# Audio & Video Media Intelligence Architecture

EnterpriseRAG ingests local audio/video files (MP4, MOV, WAV, MP3) and public YouTube URLs, producing searchable timestamped transcripts and AI chapters.

---

## Media Processing Diagram

```mermaid
flowchart TD
    subgraph Input ["Media Source"]
        FILE["Uploaded MP4 / MOV / WAV"]
        YOUTUBE["YouTube / Public URL"]
    end

    subgraph Download ["Validation & Extraction"]
        SSRF["SSRF Subnet Check"]
        YTDLP["yt-dlp Subtitle Exporter"]
        FFMPEG["ffmpeg Audio Extraction (16kHz mono WAV)"]
    end

    subgraph Transcription ["Whisper Engine"]
        SUBTITLE_CHECK{"Subtitles Available?"}
        PARSER["VTT / SRT Subtitle Parser"]
        WHISPER["faster-whisper Small Model (CPU int8)"]
    end

    subgraph Intelligence ["Indexing & Chapter Analysis"]
        SEGMENTS["Timestamp Segments (start, end, text)"]
        CHAPTERS["AI Chapter Segmentation & Action Items"]
        VECTOR["Vector Chunks with Timestamp Metadata"]
    end

    FILE --> FFMPEG
    YOUTUBE --> SSRF --> YTDLP
    YTDLP --> SUBTITLE_CHECK
    SUBTITLE_CHECK -- Yes --> PARSER --> SEGMENTS
    SUBTITLE_CHECK -- No --> FFMPEG --> WHISPER --> SEGMENTS
    
    SEGMENTS --> CHAPTERS
    SEGMENTS --> VECTOR
```

---

## Key Output Features
- **Interactive Player Sync**: Clicking a citation timestamp jumps video playback directly to that position.
- **Transcript Search**: Instant lexical search over full video transcripts.
- **Export Options**: Export transcripts to Markdown, TXT, or JSON formats.
