#!/bin/bash

echo "Starting KubeSim Frontend initialization..."

# Navigate to the React app directory
cd kubesim || {
  echo "Error: kubesim directory not found!"
  exit 1
}

# Check if npm is installed
if ! command -v npm &> /dev/null; then
  echo "Error: npm is not installed. Please install Node.js and npm to run the frontend."
  exit 1
fi

# Copy the config.json file from root to public directory for frontend access
echo "Copying config.json to public directory..."
cp ../config.json public/ || {
  echo "Warning: Could not copy config.json to public directory"
}

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

# Start the React development server
echo "Starting React development server on port 3000..."
npm start

# Kill any running processes
pkill -f "npm start"
# Start the frontend again
./start-frontend.sh 