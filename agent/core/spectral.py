# agent/core/spectral.py
import numpy as np
import torch
import torch.func
from typing import Callable


def spectral_radius(matrix: np.ndarray) -> float:
    """Return the spectral radius (max |eigenvalue|)."""
    eigs = np.linalg.eigvals(matrix)
    return float(max(abs(eigs)))


def full_jacobian(f: Callable, x: torch.Tensor) -> torch.Tensor:
    """Compute the full Jacobian matrix of function f at point x.
    
    Parameters
    ----------
    f : Callable
        Function to compute Jacobian for. Should take a tensor input
        and return a tensor output.
    x : torch.Tensor
        Point at which to evaluate the Jacobian.
        
    Returns
    -------
    torch.Tensor
        Jacobian matrix of shape (output_dim, input_dim)
    """
    return torch.func.jacfwd(f)(x)


def estimate_spectral_radius(
    f: Callable, 
    x: torch.Tensor, 
    n_iter: int = 5
) -> float:
    """Estimate spectral radius using power iteration on Jacobian-vector products.
    
    This function uses the power iteration method to estimate the largest eigenvalue
    (in magnitude) of the Jacobian matrix of f at point x, without explicitly
    computing the full Jacobian matrix.
    
    Parameters
    ----------
    f : Callable
        Function to analyze. Should take a tensor input and return a tensor output.
    x : torch.Tensor
        Point at which to evaluate the Jacobian.
    n_iter : int, optional
        Number of power iterations (default: 5)
        
    Returns
    -------
    float
        Estimated spectral radius (largest eigenvalue magnitude)
    """
    # Ensure x requires gradients
    x = x.detach().requires_grad_(True)
    
    # Get function output to determine dimensions
    y = f(x)
    input_dim = x.numel()
    output_dim = y.numel()
    
    # For non-square Jacobians, we need to consider the appropriate matrix
    # For power iteration, we'll use J^T @ J for rectangular matrices
    is_square = (input_dim == output_dim)
    
    # Initialize random vector for power iteration
    torch.manual_seed(42)  # For reproducibility
    if is_square:
        v = torch.randn(input_dim, dtype=x.dtype, device=x.device)
    else:
        # For rectangular matrices, work with J^T @ J (which is square)
        v = torch.randn(input_dim, dtype=x.dtype, device=x.device)
    
    # Normalize initial vector
    v = v / torch.norm(v)
    
    # Power iteration
    for _ in range(n_iter):
        # Flatten x for JVP computation
        x_flat = x.view(-1)
        
        # Define function that operates on flattened inputs
        def f_flat(x_flat_inner):
            x_reshaped = x_flat_inner.view(x.shape)
            return f(x_reshaped).view(-1)
        
        if is_square:
            # For square matrices: compute J @ v using JVP
            _, jvp_result = torch.func.jvp(f_flat, (x_flat,), (v,))
            v_new = jvp_result
        else:
            # For rectangular matrices: compute J^T @ (J @ v)
            # First compute J @ v
            _, jv = torch.func.jvp(f_flat, (x_flat,), (v,))
            
            # Then compute J^T @ (J @ v) using VJP
            _, vjp_fn = torch.func.vjp(f_flat, x_flat)
            v_new = vjp_fn(jv)[0]
        
        # Normalize
        norm = torch.norm(v_new)
        if norm > 1e-10:  # Avoid division by zero
            v = v_new / norm
        else:
            break
    
    # Estimate eigenvalue: v^T @ (matrix @ v) / (v^T @ v)
    x_flat = x.view(-1)
    def f_flat(x_flat_inner):
        x_reshaped = x_flat_inner.view(x.shape)
        return f(x_reshaped).view(-1)
    
    if is_square:
        _, jvp_result = torch.func.jvp(f_flat, (x_flat,), (v,))
        eigenval_estimate = torch.dot(v, jvp_result)
    else:
        # For rectangular matrices, the eigenvalue of J^T @ J
        _, jv = torch.func.jvp(f_flat, (x_flat,), (v,))
        _, vjp_fn = torch.func.vjp(f_flat, x_flat)
        jtjv = vjp_fn(jv)[0]
        eigenval_estimate = torch.dot(v, jtjv)
    
    return float(torch.abs(eigenval_estimate))
