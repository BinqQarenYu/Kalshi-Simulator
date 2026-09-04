"""PyTorch QuoLas Nano Microscope Architecture for Kalshi Microstructure Inference.

Deep Residual MLP with LayerNorm and SiLU activations for 28-dimensional orderflow feature vectors.
Outputs 3-class probabilistic classification: [P(UP), P(DOWN), P(WAIT)].
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualBlock(nn.Module):
    """Residual MLP Block with LayerNorm, SiLU non-linearities, and Dropout."""

    def __init__(self, dim: int = 64, hidden_dim: int = 128, dropout: float = 0.1) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.fc1 = nn.Linear(dim, hidden_dim)
        self.act = nn.SiLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden_dim, dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.norm(x)
        out = self.fc1(out)
        out = self.act(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return residual + out


class QuoLasMicroscopeNet(nn.Module):
    """QuoLas Nano Microscope Neural Classifier.

    Input: (B, 28) normalized orderflow microstructure tensor.
    Output: (B, 3) softmax probabilities for [UP, DOWN, WAIT].
    """

    def __init__(
        self,
        input_dim: int = 28,
        hidden_dim: int = 64,
        num_classes: int = 3,
        num_blocks: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_classes = num_classes

        # Input projection layer
        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Dropout(dropout),
        )

        # Residual backbone blocks
        self.blocks = nn.ModuleList([
            ResidualBlock(dim=hidden_dim, hidden_dim=hidden_dim * 2, dropout=dropout)
            for _ in range(num_blocks)
        ])

        # Classification head
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor, return_logits: bool = False) -> torch.Tensor:
        """Forward pass through the neural network.

        Args:
            x: Input tensor of shape (B, 28).
            return_logits: If True, returns raw unnormalized logits; otherwise returns softmax probabilities.

        Returns:
            torch.Tensor: (B, 3) classification outputs.
        """
        h = self.input_layer(x)
        for block in self.blocks:
            h = block(h)
        logits = self.head(h)

        if return_logits:
            return logits
        return F.softmax(logits, dim=-1)


class ExportableQuoLasNet(nn.Module):
    """Dual-input wrapper for QuoLasMicroscopeNet to export seamless ONNX graphs.

    Inputs:
        spatial_input: (B, 15) - 15-level spatial orderbook imbalance
        toxic_input: (B, 13) - 13-parameter toxic microstructure vector
    Output:
        action_logits: (B, 3) - unnormalized directional logits [UP, DOWN, WAIT]
    """

    def __init__(self, backbone: QuoLasMicroscopeNet) -> None:
        super().__init__()
        self.backbone = backbone

    def forward(
        self,
        spatial_input: torch.Tensor,
        toxic_input: torch.Tensor,
    ) -> torch.Tensor:
        # Note: Feature extractor orders the 28-D vector as:
        # [:13] toxic features, [13:28] spatial imbalances.
        # Concatenate along feature dimension to reconstruct the (B, 28) representation.
        x = torch.cat([toxic_input, spatial_input], dim=-1)
        return self.backbone(x, return_logits=True)
