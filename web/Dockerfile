# AI Notebook Platform - Web Frontend Dockerfile

FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Development mode with hot reload
CMD ["npm", "run", "dev"]
