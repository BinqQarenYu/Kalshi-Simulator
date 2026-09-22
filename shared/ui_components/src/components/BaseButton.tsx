import React from 'react';
export const BaseButton = ({ children }: { children: React.ReactNode }) => (
  <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 font-mono">
    {children}
  </button>
);
