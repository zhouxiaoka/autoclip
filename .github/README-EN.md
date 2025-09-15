# AutoClip - AI Video Intelligent Clipping System

![AutoClip Logo](https://img.shields.io/badge/AutoClip-AI%20Video%20Processing-blue?style=for-the-badge&logo=video)

## AI-powered intelligent video clipping system

Supporting YouTube/Bilibili video download, automatic clipping, and smart collection
generation

[![Python](https://img.shields.io/badge/Python-3.8+-green?style=flat&logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18+-blue?style=flat&logo=react)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-red?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue?style=flat&logo=typescript)](https://www.typescriptlang.org)
[![Celery](https://img.shields.io/badge/Celery-Latest-green?style=flat&logo=celery)](https://celeryproject.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

[![GitHub stars](https://img.shields.io/badge/Stars-0-blue?style=social)](https://github.com/zhouxiaoka/autoclip)
[![GitHub forks](https://img.shields.io/badge/Forks-0-blue?style=social)](https://github.com/zhouxiaoka/autoclip)
[![GitHub issues](https://img.shields.io/badge/Issues-0-blue)](https://github.com/zhouxiaoka/autoclip/issues)

**Language**: [English](README-EN.md) | [中文](README.md)

</div>

## 🎯 Project Overview

AutoClip is an AI-powered intelligent video clipping system that can automatically
download videos from YouTube, Bilibili, and other platforms, extract exciting clips
through AI analysis, and intelligently generate collections. The system adopts a
modern frontend-backend separation architecture, providing an intuitive web
interface and powerful backend processing capabilities.

### ✨ Core Features

- 🎬 **Multi-platform Support**: One-click download from YouTube, Bilibili, and local
  file upload
- 🤖 **AI Intelligent Analysis**: Video content understanding based on Qwen large
  language model
- ✂️ **Automatic Clipping**: Intelligent recognition of exciting clips with automatic
  cutting, supporting multiple video categories
- 📚 **Smart Collections**: AI-recommended and manually created video collections
  with drag-and-drop sorting
- 🚀 **Real-time Processing**: Asynchronous task queue with real-time progress feedback
  and WebSocket communication
- 🎨 **Modern Interface**: React + TypeScript + Ant Design with responsive design
- 📱 **Mobile Support** **[In Development]**: Responsive design, improving mobile
  experience
- 🔐 **Account Management** **[In Development]**: Support for multiple Bilibili account
  management with automatic health checks
- 📊 **Data Statistics**: Complete project management and data statistics functionality
- 🛠️ **Easy Deployment**: One-click startup scripts, Docker support, and detailed
  documentation
- 📤 **Bilibili Upload** **[In Development]**: Automatic upload of clipped videos
  to Bilibili
- ✏️ **Subtitle Editing** **[In Development]**: Visual subtitle editing and
  synchronization functionality

## 🏗️ System Architecture

```mermaid
graph TB
    A[User Interface] --> B[FastAPI Backend]
    B --> C[Celery Task Queue]
    B --> D[Redis Cache]
    B --> E[SQLite Database]
    C --> F[AI Processing Engine]
    F --> G[Video Processing]
    F --> H[Subtitle Analysis]
    F --> I[Content Understanding]
    B --> J[File Storage]
    K[YouTube API] --> B
    L[Bilibili API] --> B
```

### Technology Stack

#### Backend Technologies

- **FastAPI**: Modern Python web framework with automatic API documentation generation
- **Celery**: Distributed task queue supporting asynchronous processing
- **Redis**: Message broker and cache for task status management
- **SQLite**: Lightweight database with PostgreSQL upgrade support
- **yt-dlp**: YouTube video download supporting multiple formats
- **Qwen**: AI content analysis supporting multiple models
- **WebSocket**: Real-time communication and progress push
- **Pydantic**: Data validation and serialization

#### Frontend Technologies

- **React 18**: User interface framework with Hooks and functional components
- **TypeScript**: Type safety for better development experience
- **Ant Design**: Enterprise-grade UI component library
- **Vite**: Fast build tool with hot reload
- **Zustand**: Lightweight state management
- **React Router**: Route management
- **Axios**: HTTP client
- **React Player**: Video player

## 🚀 Quick Start

### Environment Requirements

#### Docker Deployment (Recommended)

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Memory**: Minimum 4GB, recommended 8GB+
- **Storage**: Minimum 10GB available space

#### Local Deployment

- **Operating System**: macOS / Linux / Windows (WSL)
- **Python**: 3.8+ (recommended 3.9+)
- **Node.js**: 16+ (recommended 18+)
- **Redis**: 6.0+ (recommended 7.0+)
- **FFmpeg**: Video processing dependency
- **Memory**: Minimum 4GB, recommended 8GB+
- **Storage**: Minimum 10GB available space

### One-Click Startup

#### Method 1: Docker Deployment (Recommended)

```bash
# Clone the project
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip

# Docker one-click startup
./docker-start.sh

# Development environment startup
./docker-start.sh dev

# Stop services
./docker-stop.sh

# Check service status
./docker-status.sh
```

#### Method 2: Local Deployment

```bash
# Clone the project
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip

# One-click startup (recommended, includes complete checks and monitoring)
./start_autoclip.sh

# Quick startup (development environment, skips detailed checks)
./quick_start.sh

# Check system status
./status_autoclip.sh

# Stop system
./stop_autoclip.sh
```

### Manual Installation

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install frontend dependencies
cd frontend && npm install && cd ..

# 4. Install Redis
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server

# CentOS/RHEL
sudo yum install redis
sudo systemctl start redis

# 5. Install FFmpeg
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# 6. Configure environment variables
cp env.example .env
# Edit .env file and fill in necessary configurations
```

## 🎬 Feature Demo

### Main Feature Showcase

1. **Video Download and Processing**
   - Support for YouTube, Bilibili video link parsing
   - Automatic video and subtitle file download
   - Support for local file upload

2. **AI Intelligent Analysis**
   - Automatic video outline extraction
   - Intelligent topic timeline identification
   - Exciting clip scoring

3. **Video Clipping and Collections**
   - Automatic exciting clip generation
   - Smart collection recommendations
   - Support for manual editing and sorting

4. **Real-time Progress Monitoring**
   - WebSocket real-time progress push
   - Detailed task status display
   - Error handling and retry mechanisms

5. **Bilibili Upload Feature** **[In Development]**
   - Automatic upload of clipped videos to Bilibili
   - Support for multiple account management
   - Batch upload and queue management

6. **Subtitle Editing Feature** **[In Development]**
   - Visual subtitle editor
   - Subtitle synchronization and adjustment
   - Multi-language subtitle support

## 📖 User Guide

### 1. Video Download

#### YouTube Videos

1. Click "New Project" on the homepage
2. Select "YouTube Link"
3. Paste the video URL
4. Choose browser cookies (optional)
5. Click "Start Download"

#### Bilibili Videos

1. Click "New Project" on the homepage
2. Select "Bilibili Link"
3. Paste the video URL
4. Choose login account
5. Click "Start Download"

#### Local Files

1. Click "New Project" on the homepage
2. Select "File Upload"
3. Drag and drop or select video files
4. Upload subtitle files (optional)
5. Click "Start Processing"

### 2. Intelligent Processing

The system will automatically execute the following steps:

1. **Material Preparation**: Download video and subtitle files
2. **Content Analysis**: AI extracts video outline and key information
3. **Timeline Extraction**: Identify topic time intervals
4. **Exciting Scoring**: AI scoring for each clip
5. **Title Generation**: Generate attractive titles for exciting clips
6. **Collection Recommendation**: AI-recommended video collections
7. **Video Generation**: Generate clipped videos and collection videos

### 3. Result Management

- **View Clips**: View all generated video clips on the project detail page
- **Edit Information**: Modify clip titles, descriptions, etc.
- **Create Collections**: Manually create or use AI-recommended collections
- **Download Export**: Download individual clips or complete collections
- **Bilibili Upload** **[In Development]**: One-click upload of clipped videos to
  Bilibili
- **Subtitle Editing** **[In Development]**: Visual editing and synchronization of
  subtitle files

## 🔧 Configuration

### Environment Variable Configuration

Create `.env` file:

```bash
# Database configuration
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis configuration
REDIS_URL=redis://localhost:6379/0

# AI API configuration
API_DASHSCOPE_API_KEY=your_dashscope_api_key
API_MODEL_NAME=qwen-plus

# Logging configuration
LOG_LEVEL=INFO
ENVIRONMENT=development
DEBUG=true

# File storage
UPLOAD_DIR=./data/uploads
PROJECT_DIR=./data/projects
```

### Bilibili Account Configuration **[In Development]**

1. Click "Bilibili Account Management" on the settings page
2. Choose login method:
   - **Cookie Import** (recommended): Export cookies from browser
   - **Account Password**: Directly input account and password
   - **QR Code Login**: Scan QR code to login
3. After successful addition, the system will automatically manage account health
  status

## 📁 Project Structure

```text
autoclip/
├── backend/                 # Backend code
│   ├── api/                # API routes
│   │   ├── v1/            # API v1 version
│   │   │   ├── youtube.py # YouTube download API
│   │   │   ├── bilibili.py # Bilibili download API
│   │   │   ├── projects.py # Project management API
│   │   │   ├── clips.py   # Video clip API
│   │   │   ├── collections.py # Collection management API
│   │   │   └── settings.py # System settings API
│   │   └── upload_queue.py # Upload queue management
│   ├── core/              # Core configuration
│   │   ├── database.py    # Database configuration
│   │   ├── celery_app.py  # Celery configuration
│   │   ├── config.py      # System configuration
│   │   └── llm_manager.py # AI model management
│   ├── models/            # Data models
│   │   ├── project.py     # Project model
│   │   ├── clip.py        # Clip model
│   │   ├── collection.py  # Collection model
│   │   └── bilibili.py    # Bilibili account model
│   ├── services/          # Business logic
│   │   ├── video_service.py # Video processing service
│   │   ├── ai_service.py  # AI analysis service
│   │   └── upload_service.py # Upload service
│   ├── tasks/             # Celery tasks
│   │   ├── processing.py  # Processing tasks
│   │   ├── upload.py      # Upload tasks
│   │   └── maintenance.py # Maintenance tasks
│   ├── pipeline/          # Processing pipeline
│   │   ├── step1_outline.py # Outline extraction
│   │   ├── step2_timeline.py # Timeline analysis
│   │   ├── step3_scoring.py # Exciting scoring
│   │   └── step6_video.py # Video generation
│   └── utils/             # Utility functions
├── frontend/              # Frontend code
│   ├── src/
│   │   ├── components/    # React components
│   │   │   ├── UploadModal.tsx # Upload modal
│   │   │   ├── ClipCard.tsx # Clip card
│   │   │   ├── CollectionCard.tsx # Collection card
│   │   │   └── BilibiliManager.tsx # Bilibili management
│   │   ├── pages/         # Page components
│   │   │   ├── HomePage.tsx # Home page
│   │   │   ├── ProjectDetailPage.tsx # Project detail
│   │   │   └── SettingsPage.tsx # Settings page
│   │   ├── services/      # API services
│   │   │   └── api.ts     # API client
│   │   └── stores/        # State management
│   └── package.json
├── data/                  # Data storage
│   ├── projects/          # Project data
│   ├── uploads/           # Upload files
│   ├── temp/              # Temporary files
│   ├── output/            # Output files
│   └── autoclip.db        # Database file
├── scripts/               # Utility scripts
│   ├── start_autoclip.sh  # Startup script
│   ├── stop_autoclip.sh   # Stop script
│   └── status_autoclip.sh # Status check
├── docs/                  # Documentation
├── logs/                  # Log files
├── Dockerfile             # Docker image build file
├── Dockerfile.dev         # Development environment Docker file
├── docker-compose.yml     # Production environment Docker orchestration
├── docker-compose.dev.yml # Development environment Docker orchestration
├── docker-start.sh        # Docker startup script
├── docker-stop.sh         # Docker stop script
├── docker-status.sh       # Docker status check script
├── .dockerignore          # Docker ignore file
├── DOCKER.md              # Docker deployment documentation
└── *.sh                   # Startup scripts
```

## 🌐 API Documentation

After starting the system, visit the following addresses to view API documentation:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Main API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/projects` | GET | Get project list |
| `/api/v1/projects` | POST | Create new project |
| `/api/v1/projects/{id}` | GET | Get project details |
| `/api/v1/youtube/parse` | POST | Parse YouTube video information |
| `/api/v1/youtube/download` | POST | Download YouTube video |
| `/api/v1/bilibili/download` | POST | Download Bilibili video |
| `/api/v1/projects/{id}/process` | POST | Start project processing |
| `/api/v1/projects/{id}/status` | GET | Get processing status |

## 🔍 Troubleshooting

### Common Issues

#### 1. Port Occupied

```bash
# Check port usage
lsof -i :8000  # Backend port
lsof -i :3000  # Frontend port

# Stop occupying processes
kill -9 <PID>
```

#### 2. Redis Connection Failed

```bash
# Check Redis status
redis-cli ping

# Start Redis service
brew services start redis  # macOS
systemctl start redis-server  # Linux
```

#### 3. YouTube Download Failed

- Check network connection
- Update yt-dlp: `pip install --upgrade yt-dlp`
- Try using browser cookies
- Check if video is available

#### 4. Bilibili Download Failed

- Check account login status
- Update account cookies
- Check video permission settings

### Log Viewing

```bash
# View all logs
tail -f logs/*.log

# View specific service logs
tail -f logs/backend.log    # Backend logs
tail -f logs/frontend.log   # Frontend logs
tail -f logs/celery.log     # Task queue logs
```

### System Status Check

```bash
# Detailed status check
./status_autoclip.sh

# Manual service check
curl http://localhost:8000/api/v1/health/  # Backend health check
curl http://localhost:3000/                # Frontend access test
redis-cli ping                             # Redis connection test
```

## 🛠️ Development Guide

### Backend Development

```bash
# Activate virtual environment
source venv/bin/activate

# Set Python path
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Start backend development server
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend Development

```bash
# Enter frontend directory
cd frontend

# Start development server
npm run dev
```

### Celery Worker

```bash
# Start Worker
celery -A backend.core.celery_app worker --loglevel=info

# Start Beat scheduler
celery -A backend.core.celery_app beat --loglevel=info

# Start Flower monitoring
celery -A backend.core.celery_app flower --port=5555
```

## 📊 Performance Optimization

### Production Environment Configuration

1. **Database Optimization**
   - Use PostgreSQL instead of SQLite
   - Configure connection pooling
   - Enable query caching

2. **Redis Optimization**
   - Configure memory limits
   - Enable persistence
   - Set expiration policies

3. **Celery Optimization**
   - Adjust concurrency
   - Configure task routing
   - Enable result backend

## 🔒 Security Configuration

### Production Environment Security

1. **Environment Variables**
   - Use strong passwords
   - Regularly rotate keys
   - Limit API access

2. **Network Security**
   - Configure firewall
   - Use HTTPS
   - Limit CORS

3. **Data Security**
   - Regular backups
   - Encrypt sensitive data
   - Access control

## 🚀 Deployment Guide

### Docker Deployment

#### Quick Start

```bash
# Clone the project
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip

# Configure environment variables
cp env.example .env
# Edit .env file and fill in necessary configurations

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

#### Access Services

- **Frontend Interface**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Flower Monitoring**: [http://localhost:5555](http://localhost:5555)

#### Development Environment

```bash
# Use development environment configuration
docker-compose -f docker-compose.dev.yml up -d

# View logs in real-time
docker-compose -f docker-compose.dev.yml logs -f
```

#### Detailed Instructions

Complete Docker deployment guide please refer to [DOCKER.md](DOCKER.md) documentation.

### System Service

```bash
# Create systemd service file
sudo nano /etc/systemd/system/autoclip.service

[Unit]
Description=AutoClip Video Processing System
After=network.target redis.service

[Service]
Type=forking
User=autoclip
WorkingDirectory=/opt/autoclip
ExecStart=/opt/autoclip/start_autoclip.sh
ExecStop=/opt/autoclip/stop_autoclip.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📈 Roadmap

### Coming Soon

- [ ] **Bilibili Upload Feature**: Automatic upload of clipped videos to Bilibili
  with multi-account management
- [ ] **Subtitle Editing Feature**: Visual subtitle editor and synchronization functionality
- [ ] **Multi-language Support**: Support for more language video processing
- [ ] **Cloud Storage**: Integrate cloud storage services
- [ ] **Batch Processing**: Support for batch video processing
- [ ] **API Open**: Provide public API interface
- [ ] **Mobile App**: Develop mobile application

### Long-term Planning

- [ ] **AI Model Optimization**: Integrate more AI models
- [ ] **Real-time Collaboration**: Support multi-user collaboration
- [ ] **Plugin System**: Support third-party plugins
- [ ] **Enterprise Edition**: Enterprise-level features and services

## 🤝 Contributing

We welcome all forms of contributions! Whether it's code contributions,
documentation improvements, issue reports, or feature suggestions.

### How to Contribute

1. **Fork** the project to your GitHub account
2. Clone your Fork to local:

   ```bash
   git clone https://github.com/zhouxiaoka/autoclip.git
   cd autoclip
   ```

3. Create feature branch:

   ```bash
   git checkout -b feature/amazing-feature
   ```

4. Develop and test
5. Commit changes:

   ```bash
   git add .
   git commit -m 'feat: add amazing feature'
   ```

6. Push branch:

   ```bash
   git push origin feature/amazing-feature
   ```

7. Create **Pull Request** on GitHub

### Development Standards

#### Code Standards

- Backend: Follow PEP 8 Python code standards
- Frontend: Use TypeScript, follow ESLint rules
- Commit messages: Use conventional commit format (feat, fix, docs, style, refactor,
  test, chore)

#### Development Process

1. Ensure all tests pass
2. Add necessary test cases
3. Update related documentation
4. Ensure code quality checks pass

#### Commit Message Format

```text
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Examples:

- `feat(api): add video download endpoint`
- `fix(ui): resolve upload modal display issue`
- `docs(readme): update installation instructions`

## ❓ FAQ

### Installation and Startup Issues

**Q: What to do when ports are occupied during startup?**
A: Use the following commands to check and stop processes occupying ports:

```bash
# Check port usage
lsof -i :8000  # Backend port
lsof -i :3000  # Frontend port

# Stop processes
kill -9 <PID>
```

**Q: What to do when Redis connection fails?**
A: Ensure Redis service is running:

```bash
# Check Redis status
redis-cli ping

# Start Redis service
brew services start redis  # macOS
sudo systemctl start redis-server  # Linux
```

**Q: What to do when frontend dependency installation fails?**
A: Try clearing cache and reinstalling:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### Feature Usage Issues

**Q: What to do when YouTube video download fails?**
A:

1. Check network connection
2. Update yt-dlp: `pip install --upgrade yt-dlp`
3. Try using browser cookies
4. Check if video is available or requires login

**Q: What to do when Bilibili video download fails?**
A:

1. Check account login status
2. Update account cookies
3. Check video permission settings
4. Try using other accounts

**Q: What to do when AI processing is slow?**
A:

1. Check API key configuration
2. Adjust processing parameters (reduce chunk_size)
3. Check network connection
4. Consider using faster AI models

**Q: When will Bilibili upload feature be available?**
A: Bilibili upload feature is currently in development and is expected to be
released in the next version. This feature will support:

- Automatic upload of clipped videos to Bilibili
- Multi-account management and switching
- Batch upload and queue management
- Upload progress monitoring

**Q: When will subtitle editing feature be available?**
A: Subtitle editing feature is currently in development and is expected to be
released in the next version. This feature will support:

- Visual subtitle editor
- Subtitle timeline synchronization
- Multi-language subtitle support
- Subtitle format conversion

### Performance Optimization

**Q: How to improve processing speed?**
A:

1. Increase Celery Worker concurrency
2. Use SSD storage
3. Increase system memory
4. Optimize video quality settings

**Q: How to reduce storage space usage?**
A:

1. Regularly clean temporary files
2. Compress output videos
3. Delete unnecessary projects
4. Use external storage

## 📞 Support & Feedback

### Get Help

- **Issue Reports**: [GitHub Issues](https://github.com/zhouxiaoka/autoclip/issues)
- **Feature Suggestions**: [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions)
- **Bug Reports**: Please use GitHub Issues template
- **Documentation**: [Project Documentation](docs/)

### Contact

For questions or suggestions, please contact us through:

#### 💬 QQ

<img src="./qq_qr.jpg" alt="QQ二维码" width="150">

#### 📱 Feishu

<img src="./feishu_qr.jpg" alt="飞书二维码" width="150">

#### 📧 Other Contact Methods

- Submit a [GitHub Issue](https://github.com/zhouxiaoka/autoclip/issues)
- Send email to: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)
- Add the above QQ or Feishu contact

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgments

Thanks to the following open source projects and services:

### Core Technology Stack

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://reactjs.org/) - User interface library
- [Ant Design](https://ant.design/) - Enterprise-grade UI design language
- [TypeScript](https://typescriptlang.org/) - JavaScript superset
- [Celery](https://docs.celeryproject.org/) - Distributed task queue
- [Redis](https://redis.io/) - In-memory data structure store

### Video Processing

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube video download tool
- [FFmpeg](https://ffmpeg.org/) - Audio and video processing framework

### AI Services

- [Qwen](https://tongyi.aliyun.com/) - Alibaba Cloud large language model service
- [DashScope](https://dashscope.aliyun.com/) - Alibaba Cloud AI service platform

### Development Tools

- [Vite](https://vitejs.dev/) - Frontend build tool
- [Zustand](https://github.com/pmndrs/zustand) - State management library
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation library

### Special Thanks

- All developers contributing to the open source community
- Users providing feedback and suggestions
- Community members participating in testing and code contributions

---

## If this project helps you, please give us a ⭐ Star

[![Star History Chart](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

Made with ❤️ by AutoClip Team

⭐ If you find it useful, please give us a Star!
