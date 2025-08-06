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
    
    def estimate_spectral_radius(
        self, 
        x: torch.Tensor, 
        n_iter: int = 6,
        tolerance: float = 1e-6,
        batch_mode: bool = False
    ) -> float:
        """Estimate spectral radius using power iteration.
        
        Parameters
        ----------
        x : torch.Tensor
            Input point(s) for evaluation. Can be 1D vector or batch of vectors.
        n_iter : int, optional
            Maximum number of power iterations (default: 6)
        tolerance : float, optional
            Convergence tolerance for early stopping (default: 1e-6)
        batch_mode : bool, optional
            If True, handle x as batch of inputs and return averaged spectral radius
            
        Returns
        -------
        float
            Estimated spectral radius
        """
        if batch_mode or x.dim() > 1:
            # Handle batch mode - process each sample and return average
            if x.dim() == 1:
                # Single vector case
                return self._estimate_single_spectral_radius(x, n_iter, tolerance)
            else:
                # Batch case - process each sample
                batch_size = x.shape[0]
                spectral_radii = []
                
                for i in range(batch_size):
                    x_i = x[i]
                    rho_i = self._estimate_single_spectral_radius(x_i, n_iter, tolerance)
                    spectral_radii.append(rho_i)
                
                # Return average spectral radius across batch
                return float(torch.tensor(spectral_radii).mean())
        else:
            # Single input case
            return self._estimate_single_spectral_radius(x, n_iter, tolerance)
    
    def _estimate_single_spectral_radius(
        self, 
        x: torch.Tensor, 
        n_iter: int, 
        tolerance: float
    ) -> float:
        """Estimate spectral radius for a single input vector.
        
        Parameters
        ----------
        x : torch.Tensor
            Single input vector
        n_iter : int
            Maximum number of power iterations
        tolerance : float
            Convergence tolerance for early stopping
            
        Returns
        -------
        float
            Estimated spectral radius
        """
        # Ensure x is 1D and requires gradients
        if x.dim() != 1:
            raise ValueError(f"Single input must be 1D, got {x.dim()}D tensor")
        
        # Determine dimensions
        y = self(x)
        input_dim = x.numel()
        output_dim = y.numel()
        is_square = (input_dim == output_dim)
        
        # Initialize random vector for power iteration with device-aware generator
        g = torch.Generator(device=x.device)
        g.manual_seed(torch.randint(0, 2**31-1, (1,), device=x.device).item())
        v = torch.randn(input_dim, generator=g, device=x.device, dtype=x.dtype)
        v = v / v.norm()
        
        # Flatten x for consistent handling
        x_flat = x.view(-1)
        
        def model_flat(x_flat_inner):
            x_reshaped = x_flat_inner.view(x.shape)
            return self(x_reshaped).view(-1)
        
        # Power iteration with convergence checking
        prev_rho = 0.0
        
        for iteration in range(n_iter):
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
            
            # Estimate current spectral radius for convergence check
            if iteration > 0:  # Skip first iteration
                if is_square:
                    _, jv_check = jvp(model_flat, (x_flat,), (v,))
                    current_rho = float(torch.abs(torch.dot(v, jv_check)))
                else:
                    _, jv_check = jvp(model_flat, (x_flat,), (v,))
                    _, jtjv_check = vjp(model_flat, x_flat, jv_check)
                    current_rho = float(torch.sqrt(torch.abs(torch.dot(v, jtjv_check))))
                
                # Check convergence
                if abs(current_rho - prev_rho) < tolerance:
                    break
                    
                prev_rho = current_rho
        
        # Final eigenvalue estimate
        if is_square:
            _, jv = jvp(model_flat, (x_flat,), (v,))
            eigenval_estimate = torch.dot(v, jv)
            return float(torch.abs(eigenval_estimate))
        else:
            _, jv = jvp(model_flat, (x_flat,), (v,))
            _, jtjv = vjp(model_flat, x_flat, jv)
            eigenval_estimate = torch.dot(v, jtjv)
            # Return sqrt for J^T @ J to get singular value (spectral radius of J)
            return float(torch.sqrt(torch.abs(eigenval_estimate)))
    
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