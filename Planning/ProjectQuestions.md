# YouTube Archive - Project Requirements & Decisions

This document captures the project scope and feature decisions based on requirements analysis.

## Project Scope & Purpose

### 1. Primary Use Case

**What's the main goal of this project?**

- ✅ **Personal archive/backup of YouTube content**
- ❌ Data analysis and insights
- ❌ Content migration to another platform
- ❌ Research purposes

### 2. Target Users

**Who will be using this tool?**

- ✅ **Just yourself (personal use)**
- ❌ Other developers
- ❌ Non-technical users (would need UI)

## Features & Functionality

### 3. Metadata Extraction

**Which specific metadata do you need?**

- ✅ **Basic video info** (title, description, duration, upload date)
- ✅ **Playlist structure and organization**
- ✅ **Thumbnails**
- ✅ **Captions/subtitles**
- ❌ Statistics (views, likes, comments count)
- ❌ Channel information
- ❌ Comments

### 4. Video Download Features

**For the actual video downloads:**

- **Quality:** 1080p
- **Audio-only option:** Not needed
- **Batch download capabilities:** Future versions
- **Resume interrupted downloads:** Future versions
- **Format preferences:** TBD (will use automatic selection)

### 5. Data Storage

**How do you want to store the extracted data?**

- ✅ **Local file system with specific folder structure**
- ✅ **Metadata and videos in same location** (for now)
- ❌ Database (SQLite, PostgreSQL, etc.)
- 🔄 **Cloud storage integration** (future versions)

## Technical Requirements

### 6. API Approach

**Technology choices:**

- ✅ **YouTube Data API v3** (official) - primary choice
- ✅ **yt-dlp for video downloads** - recommended approach
- ⚠️ **API quotas/rate limits** - need to manage carefully

### 7. Scale & Performance

**Processing expectations:**

- **Volume:** Up to a few hundred videos
- **Processing type:** Batch jobs
- **Concurrency:** Future versions
- **Real-time processing:** Not needed

### 8. Additional Features

**Current scope decisions:**

- ✅ **Progress tracking** (Phase 1)
- 🔄 **Resumability** (future versions)
- ❌ Scheduling/automation
- ❌ Filtering capabilities
- ❌ Export functionality (CSV, JSON)

---

## Summary

**Project Focus:**
- Personal YouTube content archiving tool
- CLI-based interface
- Local file storage with organized structure
- 1080p video quality with metadata preservation
- Batch processing approach
- Built for reliability and simplicity

**Future Enhancements:**
- Batch download capabilities
- Resume functionality
- Cloud storage integration
- Concurrent processing
•  Error handling and retry mechanisms? Yes.
•  Notification system for completed tasks? No.
1. Interface: 
•  CLI only? Yes
•  Web interface? No.
•  REST API? Yes.
•  All of the above?
1.  Compliance & Ethics:
◦  Is this for content you own or have permission to download? Yes.
◦  Any specific compliance requirements? None.
◦  Should the tool respect video availability (private/deleted videos)? Ideally, but have a service that documents these things in a sort of work plan. 