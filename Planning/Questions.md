Questions about Project Scope & Purpose

1. Primary Use Case: What's the main goal of this project? Is it for:
•  Personal archive/backup of YouTube content? Personal archive/backup.
•  Data analysis and insights? No.
•  Content migration to another platform? No.
•  Research purposes? No.
•  Something else? No.
2. Target Users: Who will be using this tool? 
•  Just yourself? Just me.
•  Other developers? No.
•  Non-technical users (would need a UI)? No.

Questions about Features & Functionality

3. Metadata Extraction: Which specific metadata do you need?
•  Basic video info (title, description, duration, upload date)? Yes.
•  Statistics (views, likes, comments count)? No.
•  Channel information? No.
•  Playlist structure and organization? Yes.
•  Thumbnails? Yes.
•  Captions/subtitles? Yes.
•  Comments? No,
4. Video Download Features: For the actual video downloads:
•  What quality options do you need (1080p, 4K, etc.)? 1080p.
•  Audio-only option needed? no.
•  Batch download capabilities? In later versions.
•  Resume interrupted downloads? In later versions.
•  Format preferences (mp4, webm, etc.)? Not sure.
5. Data Storage: How do you want to store the extracted data?
•  Local file system with specific folder structure? Yes.
•  Database (SQLite, PostgreSQL, etc.)? No.
•  Cloud storage integration? In later versions.
•  Both metadata and videos in same location? For now, yes.

Questions about Technical Requirements

6. API Approach: 
•  Are you planning to use YouTube Data API v3 (official)? Yes, but open to suggestions.
•  Would you also consider youtube-dl/yt-dlp for video downloads? Sure.
•  Any concerns about API quotas/rate limits? Yes, some.
1. Scale & Performance:
•  How many videos/channels do you expect to process? Up to a few hundred.
•  Do you need concurrent/parallel processing? In later versions.
•  Real-time processing or batch jobs? Batch jobs.
1. Additional Features: Do you need any of these?
•  Scheduling/automation (e.g., daily checks for new videos)? No.
•  Filtering capabilities (by date, views, duration)? No.
•  Export functionality (CSV, JSON)? No.
•  Progress tracking and resumability? Progress tracking, but resumability can come in later versions.
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