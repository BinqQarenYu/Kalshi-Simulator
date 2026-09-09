/**
 * @file ResizableSplitPane.tsx
 * @description Institutional-grade responsive 3-column resizable split-pane layout component.
 *
 * Requirements fulfilled:
 * - 3 vertical panels positioned side-by-side filling 100% container width and height.
 * - Draggable splitters/gutters between Panel 1 & 2, and between Panel 2 & 3.
 * - Left/right dynamic resizing using percentage flex-basis calculations.
 * - Dual min-width constraints (percentage & pixel thresholds) preventing panel collapse.
 * - `col-resize` cursor on hover and active dragging.
 * - Visual hover and active states (glowing institutional teal line, grab pills).
 * - Pure mouse-event hooks (onMouseDown, window mousemove/mouseup) with pointer-event locking.
 * - Optional double-click on handle to reset to defaults.
 * - Optional localStorage persistence for user layouts.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';

export interface ResizableSplitPaneProps {
  /** Left panel content */
  leftPanel?: React.ReactNode;
  /** Center panel content */
  centerPanel?: React.ReactNode;
  /** Right panel content */
  rightPanel?: React.ReactNode;
  /** Alternative: exactly 3 children [left, center, right] */
  children?: [React.ReactNode, React.ReactNode, React.ReactNode] | React.ReactNode[];
  /** Default percentage sizes for [panel1, panel2, panel3]. Must sum to 100. Default: [20, 55, 25] */
  defaultSizes?: [number, number, number];
  /** Minimum percentage constraints [min1, min2, min3]. Default: [12, 25, 15] */
  minPercentageSizes?: [number, number, number];
  /** Minimum pixel widths [minPx1, minPx2, minPx3]. Default: [150, 260, 200] */
  minPixelSizes?: [number, number, number];
  /** Maximum percentage constraints [max1, max2, max3]. Default: [40, 80, 50] */
  maxPercentageSizes?: [number, number, number];
  /** Optional localStorage key to persist custom sizes across browser refreshes */
  storageKey?: string;
  /** Callback fired when resizing updates */
  onResize?: (sizes: [number, number, number]) => void;
  /** Callback fired when user releases dragging */
  onResizeEnd?: (sizes: [number, number, number]) => void;
  /** Custom class name for outer container */
  className?: string;
  /** Custom class names for individual panels [panel1, panel2, panel3] */
  panelClassNames?: [string?, string?, string?];
  /** Show live percentage pill during active drag */
  showLivePercentageBadge?: boolean;
}

export const ResizableSplitPane: React.FC<ResizableSplitPaneProps> = ({
  leftPanel,
  centerPanel,
  rightPanel,
  children,
  defaultSizes = [20, 55, 25],
  minPercentageSizes = [12, 25, 15],
  minPixelSizes = [150, 260, 200],
  maxPercentageSizes = [40, 80, 50],
  storageKey,
  onResize,
  onResizeEnd,
  className = '',
  panelClassNames = [],
  showLivePercentageBadge = true,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Derive initial sizes from localStorage if available, or defaultSizes
  const [sizes, setSizes] = useState<[number, number, number]>(() => {
    if (storageKey && typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (
            Array.isArray(parsed) &&
            parsed.length === 3 &&
            parsed.every((n) => typeof n === 'number' && !isNaN(n) && n > 0)
          ) {
            const sum = parsed[0] + parsed[1] + parsed[2];
            if (Math.abs(sum - 100) < 1.0) {
              return [parsed[0], parsed[1], parsed[2]];
            }
          }
        }
      } catch (e) {
        console.debug('Failed loading split pane sizes from storage:', e);
      }
    }
    return defaultSizes;
  });

  // Active dragging gutter index: 0 for divider 1-2, 1 for divider 2-3, null if not dragging
  const [activeGutter, setActiveGutter] = useState<0 | 1 | null>(null);
  const [hoveredGutter, setHoveredGutter] = useState<0 | 1 | null>(null);

  // Refs for tracking drag state without closure staleness
  const isDraggingRef = useRef(false);
  const activeGutterRef = useRef<0 | 1 | null>(null);
  const sizesRef = useRef<[number, number, number]>(sizes);
  sizesRef.current = sizes;

  // Resolve 3 panels from props or children
  const panelNodes = React.useMemo(() => {
    if (leftPanel !== undefined || centerPanel !== undefined || rightPanel !== undefined) {
      return [leftPanel, centerPanel, rightPanel];
    }
    if (Array.isArray(children) && children.length >= 3) {
      return [children[0], children[1], children[2]];
    }
    return [null, null, null];
  }, [leftPanel, centerPanel, rightPanel, children]);

  // Handle Mouse Drag Start
  const handleMouseDown = useCallback((gutterIndex: 0 | 1, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingRef.current = true;
    activeGutterRef.current = gutterIndex;
    setActiveGutter(gutterIndex);

    // Apply global drag styles to body to prevent text selection and cursor flickers
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  // Handle Touch Drag Start (Mobile / Touch Devices)
  const handleTouchStart = useCallback((gutterIndex: 0 | 1, e: React.TouchEvent) => {
    if (e.touches.length !== 1) return;
    isDraggingRef.current = true;
    activeGutterRef.current = gutterIndex;
    setActiveGutter(gutterIndex);
    document.body.style.userSelect = 'none';
  }, []);

  // Handle Double Click to Reset
  const handleDoubleClick = useCallback(
    (gutterIndex: 0 | 1) => {
      setSizes(defaultSizes);
      onResize?.(defaultSizes);
      onResizeEnd?.(defaultSizes);
      if (storageKey && typeof window !== 'undefined') {
        try {
          localStorage.setItem(storageKey, JSON.stringify(defaultSizes));
        } catch (e) {
          console.debug('Failed saving reset sizes:', e);
        }
      }
    },
    [defaultSizes, onResize, onResizeEnd, storageKey]
  );

  // Core resize calculator from clientX
  const updateSizesFromClientX = useCallback(
    (clientX: number) => {
      if (!isDraggingRef.current || activeGutterRef.current === null || !containerRef.current) {
        return;
      }

      const rect = containerRef.current.getBoundingClientRect();
      const containerWidth = rect.width;
      if (containerWidth <= 0) return;

      const mouseX = clientX - rect.left;
      const currentSizes = sizesRef.current;
      const gutter = activeGutterRef.current;

      if (gutter === 0) {
        // Resizing Divider 1 (Between Panel 1 and Panel 2)
        // Panel 3 remains fixed: s2 = currentSizes[2]
        const s2 = currentSizes[2];
        const availablePct = 100 - s2;

        // Calculate min constraints for Panel 1 & 2 in percentage
        const minPct0 = Math.max(minPercentageSizes[0], (minPixelSizes[0] / containerWidth) * 100);
        const maxPct0 = Math.min(maxPercentageSizes[0], availablePct - Math.max(minPercentageSizes[1], (minPixelSizes[1] / containerWidth) * 100));

        // Proposed percentage for Panel 1
        let newS0 = (mouseX / containerWidth) * 100;
        newS0 = Math.max(minPct0, Math.min(maxPct0, newS0));
        const newS1 = availablePct - newS0;

        const nextSizes: [number, number, number] = [
          parseFloat(newS0.toFixed(2)),
          parseFloat(newS1.toFixed(2)),
          s2,
        ];

        setSizes(nextSizes);
        onResize?.(nextSizes);
      } else if (gutter === 1) {
        // Resizing Divider 2 (Between Panel 2 and Panel 3)
        // Panel 1 remains fixed: s0 = currentSizes[0]
        const s0 = currentSizes[0];
        const availablePct = 100 - s0;

        // Distance from right edge represents proposed Panel 3 width
        const distanceFromRight = containerWidth - mouseX;

        // Calculate min constraints for Panel 2 & 3 in percentage
        const minPct2 = Math.max(minPercentageSizes[2], (minPixelSizes[2] / containerWidth) * 100);
        const maxPct2 = Math.min(maxPercentageSizes[2], availablePct - Math.max(minPercentageSizes[1], (minPixelSizes[1] / containerWidth) * 100));

        let newS2 = (distanceFromRight / containerWidth) * 100;
        newS2 = Math.max(minPct2, Math.min(maxPct2, newS2));
        const newS1 = availablePct - newS2;

        const nextSizes: [number, number, number] = [
          s0,
          parseFloat(newS1.toFixed(2)),
          parseFloat(newS2.toFixed(2)),
        ];

        setSizes(nextSizes);
        onResize?.(nextSizes);
      }
    },
    [maxPercentageSizes, minPercentageSizes, minPixelSizes, onResize]
  );

  // Global mouse & touch listeners
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      updateSizesFromClientX(e.clientX);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (isDraggingRef.current && e.touches.length > 0) {
        e.preventDefault();
        updateSizesFromClientX(e.touches[0].clientX);
      }
    };

    const handleEnd = () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
        activeGutterRef.current = null;
        setActiveGutter(null);

        // Restore body styles
        document.body.style.cursor = '';
        document.body.style.userSelect = '';

        const finalSizes = sizesRef.current;
        onResizeEnd?.(finalSizes);

        // Persist to localStorage if key provided
        if (storageKey && typeof window !== 'undefined') {
          try {
            localStorage.setItem(storageKey, JSON.stringify(finalSizes));
          } catch (e) {
            console.debug('Failed saving split pane sizes to storage:', e);
          }
        }
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleEnd);
    window.addEventListener('touchmove', handleTouchMove, { passive: false });
    window.addEventListener('touchend', handleEnd);
    window.addEventListener('touchcancel', handleEnd);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleEnd);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleEnd);
      window.removeEventListener('touchcancel', handleEnd);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [
    storageKey,
    onResizeEnd,
    updateSizesFromClientX,
  ]);

  return (
    <div
      ref={containerRef}
      className={`relative flex flex-row w-full h-full overflow-hidden select-none ${className}`}
    >
      {/* =========================================================================
          PANEL 1 (LEFT)
          ========================================================================= */}
      <div
        style={{ width: `${sizes[0]}%`, minWidth: `${minPixelSizes[0]}px` }}
        className={`h-full overflow-hidden flex flex-col shrink-0 relative ${
          panelClassNames[0] || ''
        }`}
      >
        {panelNodes[0]}
      </div>

      {/* =========================================================================
          DIVIDER 1 (Between Panel 1 and Panel 2)
          ========================================================================= */}
      <div
        role="separator"
        tabIndex={0}
        aria-orientation="vertical"
        aria-valuenow={sizes[0]}
        aria-label="Resize left and center panels"
        onMouseDown={(e) => handleMouseDown(0, e)}
        onTouchStart={(e) => handleTouchStart(0, e)}
        onDoubleClick={() => handleDoubleClick(0)}
        onMouseEnter={() => setHoveredGutter(0)}
        onMouseLeave={() => setHoveredGutter(null)}
        className={`relative z-20 w-1.5 shrink-0 h-full cursor-col-resize flex items-center justify-center transition-colors duration-150 ${
          activeGutter === 0
            ? 'bg-[#00bda5] shadow-[0_0_10px_rgba(0,189,165,0.6)]'
            : hoveredGutter === 0
            ? 'bg-[#00bda5]/80'
            : 'bg-[#262d35] hover:bg-[#00bda5]/60'
        }`}
      >
        {/* Invisible expanded hit area for effortless grabbing (12px hit zone) */}
        <div className="absolute inset-y-0 -left-1.5 -right-1.5 cursor-col-resize" />

        {/* Center tactile grip pill */}
        <div
          className={`w-0.5 h-6 rounded-full transition-all duration-150 ${
            activeGutter === 0
              ? 'bg-white h-9 shadow'
              : hoveredGutter === 0
              ? 'bg-white/90 h-8'
              : 'bg-[#8c9ba5]/40'
          }`}
        />
      </div>

      {/* =========================================================================
          PANEL 2 (CENTER)
          ========================================================================= */}
      <div
        style={{ width: `${sizes[1]}%`, minWidth: `${minPixelSizes[1]}px` }}
        className={`h-full overflow-hidden flex flex-col flex-1 min-w-0 relative ${
          panelClassNames[1] || ''
        }`}
      >
        {panelNodes[1]}
      </div>

      {/* =========================================================================
          DIVIDER 2 (Between Panel 2 and Panel 3)
          ========================================================================= */}
      <div
        role="separator"
        tabIndex={0}
        aria-orientation="vertical"
        aria-valuenow={sizes[2]}
        aria-label="Resize center and right panels"
        onMouseDown={(e) => handleMouseDown(1, e)}
        onTouchStart={(e) => handleTouchStart(1, e)}
        onDoubleClick={() => handleDoubleClick(1)}
        onMouseEnter={() => setHoveredGutter(1)}
        onMouseLeave={() => setHoveredGutter(null)}
        className={`relative z-20 w-1.5 shrink-0 h-full cursor-col-resize flex items-center justify-center transition-colors duration-150 ${
          activeGutter === 1
            ? 'bg-[#00bda5] shadow-[0_0_10px_rgba(0,189,165,0.6)]'
            : hoveredGutter === 1
            ? 'bg-[#00bda5]/80'
            : 'bg-[#262d35] hover:bg-[#00bda5]/60'
        }`}
      >
        {/* Invisible expanded hit area for effortless grabbing (12px hit zone) */}
        <div className="absolute inset-y-0 -left-1.5 -right-1.5 cursor-col-resize" />

        {/* Center tactile grip pill */}
        <div
          className={`w-0.5 h-6 rounded-full transition-all duration-150 ${
            activeGutter === 1
              ? 'bg-white h-9 shadow'
              : hoveredGutter === 1
              ? 'bg-white/90 h-8'
              : 'bg-[#8c9ba5]/40'
          }`}
        />
      </div>

      {/* =========================================================================
          PANEL 3 (RIGHT)
          ========================================================================= */}
      <div
        style={{ width: `${sizes[2]}%`, minWidth: `${minPixelSizes[2]}px` }}
        className={`h-full overflow-hidden flex flex-col shrink-0 relative ${
          panelClassNames[2] || ''
        }`}
      >
        {panelNodes[2]}
      </div>

      {/* =========================================================================
          LIVE TELEMETRY PERCENTAGE BADGE (Visible during active dragging)
          ========================================================================= */}
      {showLivePercentageBadge && activeGutter !== null && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none animate-fade-in">
          <div className="px-3 py-1 rounded-full bg-[#12161a]/95 border border-[#00bda5]/50 text-[#00bda5] font-mono text-[11px] font-bold shadow-2xl flex items-center gap-2 backdrop-blur-md">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00bda5] animate-ping" />
            <span>
              {sizes[0].toFixed(0)}% │ {sizes[1].toFixed(0)}% │ {sizes[2].toFixed(0)}%
            </span>
            <span className="text-[9px] text-[#8c9ba5] font-normal">(Double-click divider to reset)</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResizableSplitPane;
