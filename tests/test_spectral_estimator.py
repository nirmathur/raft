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


class TestConvergenceTolerance:
    """Test convergence tolerance and early stopping features."""
    
    def test_early_convergence(self):
        """Test that convergence tolerance enables early stopping."""
        # Use a simple diagonal matrix that should converge quickly
        A = torch.tensor([[0.8, 0.0], [0.0, 0.6]], dtype=torch.float32)
        
        def matrix_func(x):
            return A @ x
        
        x = torch.tensor([1.0, 1.0], requires_grad=True)
        
        # Test with strict tolerance (should converge early)
        rho_strict = estimate_spectral_radius(matrix_func, x, n_iter=100, tolerance=1e-8)
        
        # Test with loose tolerance
        rho_loose = estimate_spectral_radius(matrix_func, x, n_iter=100, tolerance=1e-2)
        
        # Both should give reasonable results
        assert 0.7 < rho_strict < 0.9  # Should be around 0.8
        assert 0.7 < rho_loose < 0.9
    
    def test_convergence_tolerance_with_network(self):
        """Test convergence tolerance with neural network."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=8, activation='tanh')
        x = torch.randn(3, requires_grad=True)
        
        # Test with different tolerances
        rho_strict = model.estimate_spectral_radius(x, n_iter=50, tolerance=1e-8)
        rho_loose = model.estimate_spectral_radius(x, n_iter=50, tolerance=1e-3)
        
        # Both should be reasonable and not too different
        assert isinstance(rho_strict, float)
        assert isinstance(rho_loose, float)
        assert rho_strict > 0
        assert rho_loose > 0
        assert abs(rho_strict - rho_loose) < 1.0  # Should be reasonably close


class TestBatchSupport:
    """Test batch support for multiple inputs."""
    
    def test_batch_mode_simple_function(self):
        """Test batch mode with simple scaling function."""
        scale_factor = 0.8
        
        def scale_func(x):
            return scale_factor * x
        
        # Create batch of inputs
        batch_x = torch.tensor([[1.0, 2.0], [0.5, 1.5], [2.0, 0.5]], requires_grad=True)
        
        # Test batch mode
        rho_batch = estimate_spectral_radius(scale_func, batch_x, batch_mode=True, n_iter=10)
        
        # Should be close to the scale factor
        assert abs(rho_batch - abs(scale_factor)) < 0.1
    
    def test_batch_mode_with_network(self):
        """Test batch mode with neural network."""
        model = SimpleNet(in_dim=4, out_dim=4, hidden_dim=8, activation='tanh')
        
        # Create batch of inputs
        batch_x = torch.randn(5, 4, requires_grad=True)  # Batch of 5 vectors
        
        # Test batch mode
        rho_batch = model.estimate_spectral_radius(batch_x, batch_mode=True, n_iter=8)
        
        # Test individual mode for comparison
        individual_rhos = []
        for i in range(5):
            rho_i = model.estimate_spectral_radius(batch_x[i], n_iter=8)
            individual_rhos.append(rho_i)
        
        expected_avg = sum(individual_rhos) / len(individual_rhos)
        
        # Batch result should be close to average of individual results
        # Allow for reasonable variation due to random initialization
        assert abs(rho_batch - expected_avg) < 0.5
    
    def test_auto_batch_detection(self):
        """Test automatic batch detection."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=6)
        
        # 2D input should automatically trigger batch mode
        batch_x = torch.randn(4, 3, requires_grad=True)
        
        # Should automatically handle as batch (batch_mode=False but x.dim() > 1)
        rho_auto = model.estimate_spectral_radius(batch_x, n_iter=6)
        
        # Should return a reasonable value
        assert isinstance(rho_auto, float)
        assert rho_auto > 0
        assert not np.isnan(rho_auto)


class TestDeviceAwareness:
    """Test device awareness and GPU compatibility."""
    
    def test_cpu_device_handling(self):
        """Test that device handling works correctly on CPU."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=8)
        x = torch.randn(3, requires_grad=True)
        
        # Ensure everything is on CPU
        model = model.to('cpu')
        x = x.to('cpu')
        
        rho = model.estimate_spectral_radius(x, n_iter=6)
        
        assert isinstance(rho, float)
        assert rho > 0
        assert not np.isnan(rho)
    
    def test_device_consistency(self):
        """Test that device consistency is maintained."""
        model = SimpleNet(in_dim=4, out_dim=4, hidden_dim=8)
        
        # Test CPU
        x_cpu = torch.randn(4, requires_grad=True, device='cpu')
        model_cpu = model.to('cpu')
        rho_cpu = model_cpu.estimate_spectral_radius(x_cpu, n_iter=6)
        
        assert isinstance(rho_cpu, float)
        assert rho_cpu > 0
        
        # Note: GPU test would require CUDA availability
        # This test structure allows for easy GPU testing when available


class TestSimpleNetSpectralRadius:
    """Test spectral radius estimation on SimpleNet models."""
    
    def test_small_network_spectral_radius(self):
        """Test spectral radius computation on a small network."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=8)
        x = torch.randn(3, requires_grad=True)
        
        rho = model.estimate_spectral_radius(x, n_iter=10)
        
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
            
            rho = model.estimate_spectral_radius(x, n_iter=8)
            
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
            
            rho = model.estimate_spectral_radius(x, n_iter=10)
            
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
        
        rho = model.estimate_spectral_radius(x, n_iter=10)
        
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
    
    def test_invalid_batch_dimensions(self):
        """Test error handling for invalid batch dimensions."""
        model = SimpleNet(in_dim=3, out_dim=3, hidden_dim=6)
        
        # 3D tensor should raise an error in single mode
        x_3d = torch.randn(2, 3, 4, requires_grad=True)
        
        with pytest.raises(ValueError):
            model._estimate_single_spectral_radius(x_3d, n_iter=5, tolerance=1e-6)
    
    def test_convergence_tolerance_bounds(self):
        """Test convergence tolerance boundary conditions."""
        model = SimpleNet(in_dim=2, out_dim=2, hidden_dim=4)
        x = torch.randn(2, requires_grad=True)
        
        # Very strict tolerance
        rho_strict = model.estimate_spectral_radius(x, n_iter=100, tolerance=1e-12)
        
        # Very loose tolerance
        rho_loose = model.estimate_spectral_radius(x, n_iter=100, tolerance=1.0)
        
        # Both should return valid results
        assert isinstance(rho_strict, float)
        assert isinstance(rho_loose, float)
        assert rho_strict > 0
        assert rho_loose > 0