# GitHub Commit Generator

A Flask-based web application that authenticates users via GitHub OAuth and automates the creation of repositories with a specified number of commits. This tool is designed for testing Git workflows, educational demonstrations, or populating repositories with sample history.

## Features

- **Secure Authentication**: Integrates with GitHub OAuth to securely authenticate users without storing credentials.
- **Automated Repository Creation**: Generates new, private repositories with unique, timestamped names to avoid conflicts.
- **Bulk Commit Generation**: Automates the process of creating multiple commits by sequentially updating a file within the repository.
- **Error Handling**: Implements comprehensive error handling for network requests and GitHub API responses.

## Prerequisites

- Python 3.x
- A valid GitHub account
- A GitHub OAuth App (Client ID and Client Secret)

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/commit-generator.git
   cd GeneratorCommit
   ```

2. **Install dependencies**
   It is recommended to use a virtual environment.

   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   Create a `.env` file in the root directory based on the provided example:

   ```bash
   cp .env.example .env
   ```

   Open `.env` and configure the following variables:
   - `CLIENT_ID`: Your GitHub OAuth App Client ID.
   - `CLIENT_SECRET`: Your GitHub OAuth App Client Secret.
   - `SECRET_KEY`: A random string for Flask session security.

## Usage

1. **Start the application**

   ```bash
   python app.py
   ```

2. **Access the interface**
   Open your web browser and navigate to `http://127.0.0.1:5000`.

3. **Generate Commits**
   - Click "Login with GitHub" to authenticate.
   - On the dashboard, enter the desired number of commits.
   - Click "Generate" to start the process.
   - The application will create a new repository and populate it with the specified number of commits.

## Disclaimer

This tool is intended for educational and testing purposes only. Please use it responsibly and in accordance with GitHub's Terms of Service. Avoid using this tool to artificially inflate contribution graphs.
