"""PyTorch models for RAFT spectral analysis.

This module provides neural network architectures used for Jacobian-vector
product computations in the spectral radius estimation pipeline.
"""

import torch
import torch.nn as nn
from typing import Optional


class SimpleNet(nn.Module):
    """A simple fully-connected neural network for spectral analysis.
    
    This network provides a configurable architecture for testing
    Jacobian-vector products and spectral radius estimation.
    
    Parameters
    ----------
    in_dim : int
        Input dimension
    out_dim : int  
        Output dimension
    hidden_dim : int, optional
        Hidden layer dimension (default: 64)
    activation : str, optional
        Activation function ('relu', 'tanh', 'sigmoid') (default: 'tanh')
    """
    
    def __init__(
        self, 
        in_dim: int, 
        out_dim: int, 
        hidden_dim: int = 64,
        activation: str = 'tanh'
    ):
        super().__init__()
        
        self.in_dim = in_dim
        self.out_dim = out_dim
        
        # Define activation function
        if activation == 'relu':
            self.activation = nn.ReLU()
        elif activation == 'tanh':
            self.activation = nn.Tanh()
        elif activation == 'sigmoid':
            self.activation = nn.Sigmoid()
        else:
            raise ValueError(f"Unsupported activation: {activation}")
        
        # Network layers
        self.layers = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            self.activation,
            nn.Linear(hidden_dim, hidden_dim),
            self.activation,
            nn.Linear(hidden_dim, out_dim)
        )
        
        # Initialize weights to ensure reasonable spectral properties
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize weights with small values to ensure stable spectral radius."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                # Small uniform initialization to keep spectral radius manageable
                nn.init.uniform_(module.weight, -0.1, 0.1)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through the network.
        
        Parameters
        ----------
        x : torch.Tensor
            Input tensor of shape (..., in_dim)
            
        Returns
        -------
        torch.Tensor
            Output tensor of shape (..., out_dim)
        """
        return self.layers(x)