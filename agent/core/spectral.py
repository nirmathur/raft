# agent/core/spectral.py
import numpy as np
import torch
from torch.autograd.functional import jvp, vjp
from torch.func import jacfwd
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
    return jacfwd(f)(x)


def estimate_spectral_radius(
    f: Callable, 
    x: torch.Tensor, 
    n_iter: int = 5,
    tolerance: float = 1e-6,
    batch_mode: bool = False
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
        Point(s) at which to evaluate the Jacobian. Can be 1D vector or batch.
    n_iter : int, optional
        Maximum number of power iterations (default: 5)
    tolerance : float, optional
        Convergence tolerance for early stopping (default: 1e-6)
    batch_mode : bool, optional
        If True, handle x as batch of inputs and return averaged spectral radius
        
    Returns
    -------
    float
        Estimated spectral radius (largest eigenvalue magnitude)
    """
    if batch_mode or x.dim() > 1:
        # Handle batch mode - process each sample and return average
        if x.dim() == 1:
            # Single vector case
            return _estimate_single_spectral_radius(f, x, n_iter, tolerance)
        else:
            # Batch case - process each sample
            batch_size = x.shape[0]
            spectral_radii = []
            
            for i in range(batch_size):
                x_i = x[i]
                rho_i = _estimate_single_spectral_radius(f, x_i, n_iter, tolerance)
                spectral_radii.append(rho_i)
            
            # Return average spectral radius across batch
            return float(torch.tensor(spectral_radii).mean())
    else:
        # Single input case
        return _estimate_single_spectral_radius(f, x, n_iter, tolerance)


def _estimate_single_spectral_radius(
    f: Callable, 
    x: torch.Tensor, 
    n_iter: int, 
    tolerance: float
) -> float:
    """Estimate spectral radius for a single input vector.
    
    Parameters
    ----------
    f : Callable
        Function to analyze
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
    
    # Ensure x requires gradients
    x = x.detach().requires_grad_(True)
    
    # Get function output to determine dimensions
    y = f(x)
    input_dim = x.numel()
    output_dim = y.numel()
    
    # For non-square Jacobians, we need to consider the appropriate matrix
    # For power iteration, we'll use J^T @ J for rectangular matrices
    is_square = (input_dim == output_dim)
    
    # Initialize random vector for power iteration with fresh device-aware generator
    g = torch.Generator(device=x.device)
    g.manual_seed(torch.randint(0, 2**31-1, (1,), device=x.device).item())
    v = torch.randn(input_dim, generator=g, device=x.device, dtype=x.dtype)
    
    # Normalize initial vector
    v = v / torch.norm(v)
    
    # Flatten x for JVP computation - define once outside loop
    x_flat = x.view(-1)
    
    # Define function that operates on flattened inputs - define once outside loop
    def f_flat(x_flat_inner):
        x_reshaped = x_flat_inner.view(x.shape)
        return f(x_reshaped).view(-1)
    
    # Power iteration with convergence checking
    prev_rho = 0.0
    
    for iteration in range(n_iter):
        if is_square:
            # For square matrices: compute J @ v using JVP
            _, jvp_result = jvp(f_flat, (x_flat,), (v,))
            v_new = jvp_result
        else:
            # For rectangular matrices: compute J^T @ (J @ v)
            # First compute J @ v
            _, jv = jvp(f_flat, (x_flat,), (v,))
            
            # Then compute J^T @ (J @ v) using VJP
            _, v_new = vjp(f_flat, x_flat, jv)
        
        # Normalize
        norm = torch.norm(v_new)
        if norm > 1e-10:  # Avoid division by zero
            v = v_new / norm
        else:
            break
        
        # Estimate current spectral radius for convergence check
        if iteration > 0:  # Skip first iteration
            if is_square:
                _, jv_check = jvp(f_flat, (x_flat,), (v,))
                current_rho = float(torch.abs(torch.dot(v, jv_check)))
            else:
                _, jv_check = jvp(f_flat, (x_flat,), (v,))
                _, jtjv_check = vjp(f_flat, x_flat, jv_check)
                current_rho = float(torch.sqrt(torch.abs(torch.dot(v, jtjv_check))))
            
            # Check convergence
            if abs(current_rho - prev_rho) < tolerance:
                break
                
            prev_rho = current_rho
    
    # Estimate eigenvalue: v^T @ (matrix @ v) / (v^T @ v)
    if is_square:
        _, jvp_result = jvp(f_flat, (x_flat,), (v,))
        eigenval_estimate = torch.dot(v, jvp_result)
        return float(torch.abs(eigenval_estimate))
    else:
        # For rectangular matrices, the eigenvalue of J^T @ J
        _, jv = jvp(f_flat, (x_flat,), (v,))
        _, jtjv = vjp(f_flat, x_flat, jv)
        eigenval_estimate = torch.dot(v, jtjv)
        # Return sqrt for J^T @ J to get singular value (spectral radius of J)
        return float(torch.sqrt(torch.abs(eigenval_estimate)))
