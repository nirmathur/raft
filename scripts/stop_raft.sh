#!/bin/bash

echo "🛑 Stopping RAFT services to save RAM..."

# Stop the metrics server if running
echo "📊 Stopping metrics server..."
pkill -f "python.*metrics_server.py" 2>/dev/null || true

# Stop any running fuzz tests
echo "🧪 Stopping fuzz tests..."
pkill -f "python.*fuzz_proofs_enhanced.py" 2>/dev/null || true

# Stop Docker containers
echo "🐳 Stopping Docker containers..."
docker-compose -f docker-compose.metrics.yml down 2>/dev/null || true
docker-compose -f docker/docker-compose.yml down 2>/dev/null || true

# Stop Redis if running locally
echo "🔴 Stopping Redis..."
brew services stop redis 2>/dev/null || true
pkill redis-server 2>/dev/null || true

# Kill any remaining Python processes related to RAFT
echo "🐍 Stopping RAFT Python processes..."
pkill -f "agent.core" 2>/dev/null || true

echo "✅ All RAFT services stopped!"
echo "💾 RAM saved - you can now close for the night!"
echo ""
echo "To restart everything, run: ./scripts/start_raft.sh" 