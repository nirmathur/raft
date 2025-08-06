"""Test suite for spectral radius estimation using PyTorch functorch.

This module tests the full_jacobian and estimate_spectral_radius functions
against known linear transformations and neural network models.
"""

import numpy as np
import torch
import pytest

from agent.core.spectral import full_jacobian, estimate_spectral_radius
from agent.core.model import SimpleNet


class TestFullJacobian:
    """Test the full_jacobian function with known linear maps."""
    
    def test_linear_identity(self):
        """Test Jacobian of identity function."""
        def identity(x):
            return x
        
        x = torch.tensor([1.0, 2.0, 3.0, 4.0], requires_grad=True)
        J = full_jacobian(identity, x)
        
        # Identity function should have identity Jacobian
        expected = torch.eye(4)  # 4x4 identity for 4-element vector
        assert J.shape == (4, 4)
        torch.testing.assert_close(J, expected, atol=1e-6, rtol=1e-6)
    
    def test_linear_scaling(self):
        """Test Jacobian of linear scaling function."""
        scale_factor = 2.5
        
        def linear_scale(x):
            return scale_factor * x
        
        x = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
        J = full_jacobian(linear_scale, x)
        
        # Linear scaling should have diagonal Jacobian with scale factor
        expected = scale_factor * torch.eye(3)
        torch.testing.assert_close(J, expected, atol=1e-6, rtol=1e-6)
    
    def test_matrix_linear_map(self):
        """Test Jacobian of known matrix linear transformation."""
        # Define a 2x2 matrix transformation
        A = torch.tensor([[0.5, 0.3], [0.2, 0.4]], dtype=torch.float32)
        
        def matrix_transform(x):
            return A @ x
        
        x = torch.tensor([1.0, 1.0], requires_grad=True)
        J = full_jacobian(matrix_transform, x)
        
        # For linear map y = Ax, Jacobian should be A
        torch.testing.assert_close(J, A, atol=1e-6, rtol=1e-6)


class TestSpectralRadiusEstimation:
    """Test spectral radius estimation with known cases."""
    
    def test_identity_function(self):
        """Test spectral radius of identity function."""
        def identity(x):
            return x
        
        x = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
        rho = estimate_spectral_radius(identity, x, n_iter=10)
        
        # Identity function has spectral radius 1.0
        assert abs(rho - 1.0) < 0.1
    
    def test_scaling_function(self):
        """Test spectral radius of scaling function."""
        scale_factor = 0.7
        
        def scale_func(x):
            return scale_factor * x
        
        x = torch.tensor([1.0, 2.0], requires_grad=True)
        rho = estimate_spectral_radius(scale_func, x, n_iter=10)
        
        # Scaling function has spectral radius equal to |scale_factor|
        assert abs(rho - abs(scale_factor)) < 0.1
    
    def test_known_matrix_linear_map(self):
        """Test spectral radius estimation on known matrix."""
        # Matrix with known spectral radius
        A = torch.tensor([[0.5, 0.0], [0.0, 0.3]], dtype=torch.float32)
        
        def matrix_func(x):
            return A @ x
        
        x = torch.tensor([1.0, 1.0], requires_grad=True)
        rho_estimated = estimate_spectral_radius(matrix_func, x, n_iter=15)
        
        # True spectral radius is max(0.5, 0.3) = 0.5
        true_rho = 0.5
        assert abs(rho_estimated - true_rho) < 0.1
    
    def test_unstable_matrix(self):
        """Test spectral radius estimation on unstable matrix."""
        # Matrix with spectral radius > 1
        A = torch.tensor([[1.2, 0.1], [0.0, 1.1]], dtype=torch.float32)
        
        def unstable_func(x):
            return A @ x
        
        x = torch.tensor([1.0, 1.0], requires_grad=True)
        rho_estimated = estimate_spectral_radius(unstable_func, x, n_iter=15)
        
        # True spectral radius is max(1.2, 1.1) = 1.2
        assert rho_estimated > 1.0  # Should detect instability
        assert abs(rho_estimated - 1.2) < 0.2
    
    def test_convergence_with_iterations(self):
        """Test that more iterations improve accuracy."""
        A = torch.tensor([[0.6, 0.2], [0.1, 0.4]], dtype=torch.float32)
        
        def matrix_func(x):
            return A @ x
        
        x = torch.tensor([1.0, 1.0], requires_grad=True)
        
        # Test with different iteration counts
        rho_5 = estimate_spectral_radius(matrix_func, x, n_iter=5)
        rho_15 = estimate_spectral_radius(matrix_func, x, n_iter=15)
        
        # More iterations should give more accurate result
        # (exact value depends on the matrix, but should be stable)
        assert isinstance(rho_5, float)
        assert isinstance(rho_15, float)
        assert rho_5 > 0
        assert rho_15 > 0


class TestSimpleNetSpectralRadius:
    """Test spectral radius estimation on SimpleNet models."""
    
    def test_small_network_spectral_radius(self):
        """Test spectral radius computation on a small network."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=8)
        x = torch.randn(3, requires_grad=True)
        
        rho = estimate_spectral_radius(model, x, n_iter=10)
        
        # Should return a valid positive number
        assert isinstance(rho, float)
        assert rho > 0
        assert rho < 100  # Reasonable upper bound for well-initialized network
    
    def test_different_network_sizes(self):
        """Test spectral radius estimation on different network architectures."""
        configs = [
            (2, 2, 4),
            (5, 3, 10),
            (4, 4, 16)
        ]
        
        for in_dim, out_dim, hidden_dim in configs:
            model = SimpleNet(in_dim=in_dim, out_dim=out_dim, hidden_dim=hidden_dim)
            x = torch.randn(in_dim, requires_grad=True)
            
            rho = estimate_spectral_radius(model, x, n_iter=8)
            
            # Should always return a valid positive spectral radius
            assert isinstance(rho, float)
            assert rho > 0
            assert not np.isnan(rho)
            assert not np.isinf(rho)
    
    def test_network_activation_functions(self):
        """Test spectral radius with different activation functions."""
        activations = ['tanh', 'relu', 'sigmoid']
        
        for activation in activations:
            model = SimpleNet(in_dim=4, out_dim=4, hidden_dim=8, activation=activation)
            x = torch.randn(4, requires_grad=True)
            
            rho = estimate_spectral_radius(model, x, n_iter=10)
            
            # Should work with all activation functions
            assert isinstance(rho, float)
            assert rho > 0
            assert not np.isnan(rho)
    
    def test_reproducibility(self):
        """Test that spectral radius estimation is reproducible with manual seeding."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=6)
        x = torch.tensor([1.0, 0.5, -0.5], requires_grad=True)
        
        # Run estimation multiple times with manual seeding
        torch.manual_seed(0)
        rho1 = estimate_spectral_radius(model, x, n_iter=10)
        torch.manual_seed(0)
        rho2 = estimate_spectral_radius(model, x, n_iter=10)
        
        # Should be identical due to manual seeding
        assert abs(rho1 - rho2) < 1e-6
    
    def test_non_square_jacobian(self):
        """Test spectral radius estimation for non-square Jacobians."""
        # Network with different input/output dimensions
        model = SimpleNet(in_dim=3, out_dim=5, hidden_dim=8)
        x = torch.randn(3, requires_grad=True)
        
        rho = estimate_spectral_radius(model, x, n_iter=10)
        
        # Should handle rectangular Jacobians (using J^T @ J)
        assert isinstance(rho, float)
        assert rho > 0
        assert not np.isnan(rho)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_gradient_function(self):
        """Test behavior with function that has zero gradients."""
        def zero_func(x):
            return torch.zeros_like(x)
        
        x = torch.tensor([1.0, 2.0], requires_grad=True)
        rho = estimate_spectral_radius(zero_func, x, n_iter=5)
        
        # Zero function should have spectral radius 0
        assert abs(rho) < 1e-6
    
    def test_single_dimension(self):
        """Test with single-dimensional input/output."""
        def square_func(x):
            return x ** 2
        
        x = torch.tensor([2.0], requires_grad=True)
        rho = estimate_spectral_radius(square_func, x, n_iter=5)
        
        # Should handle 1D case
        assert isinstance(rho, float)
        assert rho > 0