"""PyTorch models for RAFT spectral analysis.

This module provides neural network architectures used for Jacobian-vector
product computations in the spectral radius estimation pipeline.
"""

import torch
import torch.nn as nn
from torch.autograd.functional import jvp, vjp
from torch.func import jacfwd
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
        
        # Define activation function and store gain for Xavier initialization
        if activation == 'relu':
            self.activation = nn.ReLU()
            self._gain = 'relu'
        elif activation == 'tanh':
            self.activation = nn.Tanh()
            self._gain = 'tanh'
        elif activation == 'sigmoid':
            self.activation = nn.Sigmoid()
            self._gain = 'sigmoid'
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
        
        # Initialize weights with Xavier/Glorot initialization
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize weights with Xavier/Glorot initialization."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                # Xavier uniform initialization with proper gain
                nn.init.xavier_uniform_(module.weight, gain=nn.init.calculate_gain(self._gain))
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
    
    def full_jacobian(self, x: torch.Tensor) -> torch.Tensor:
        """Compute the full Jacobian matrix at point x.
        
        Parameters
        ----------
        x : torch.Tensor
            Input point for Jacobian evaluation
            
        Returns
        -------
        torch.Tensor
            Jacobian matrix
        """
        return jacfwd(self)(x)
    
    def estimate_spectral_radius(self, x: torch.Tensor, n_iter: int = 6) -> float:
        """Estimate spectral radius using power iteration.
        
        Parameters
        ----------
        x : torch.Tensor
            Input point for evaluation
        n_iter : int, optional
            Number of power iterations (default: 6)
            
        Returns
        -------
        float
            Estimated spectral radius
        """
        # Determine dimensions
        y = self(x)
        input_dim = x.numel()
        output_dim = y.numel()
        is_square = (input_dim == output_dim)
        
        # Initialize random vector for power iteration
        v = torch.randn_like(x.view(-1))
        v = v / v.norm()
        
        # Flatten x for consistent handling
        x_flat = x.view(-1)
        
        def model_flat(x_flat_inner):
            x_reshaped = x_flat_inner.view(x.shape)
            return self(x_reshaped).view(-1)
        
        # Power iteration
        for _ in range(n_iter):
            if is_square:
                # For square matrices: compute J @ v using JVP
                _, jv = jvp(model_flat, (x_flat,), (v,))
                v_new = jv
            else:
                # For rectangular matrices: compute J^T @ (J @ v)
                # First compute J @ v
                _, jv = jvp(model_flat, (x_flat,), (v,))
                
                # Then compute J^T @ (J @ v) using VJP
                _, v_new = vjp(model_flat, x_flat, jv)
            
            # Normalize
            norm = v_new.norm()
            if norm > 1e-10:
                v = v_new / norm
            else:
                break
        
        # Final eigenvalue estimate
        if is_square:
            _, jv = jvp(model_flat, (x_flat,), (v,))
            eigenval_estimate = torch.dot(v, jv)
        else:
            _, jv = jvp(model_flat, (x_flat,), (v,))
            _, jtjv = vjp(model_flat, x_flat, jv)
            eigenval_estimate = torch.dot(v, jtjv)
            # Return sqrt for J^T @ J to get singular value (spectral radius of J)
            return float(torch.sqrt(torch.abs(eigenval_estimate)))
        
        return float(torch.abs(eigenval_estimate))
    
    def to_device(self, device: torch.device) -> 'SimpleNet':
        """Move model to device and return self for chaining.
        
        Parameters
        ----------
        device : torch.device
            Target device
            
        Returns
        -------
        SimpleNet
            Self for method chaining
        """
        self.to(device)
        return self