# Conversational AI & Chat Components (Member 4)

This folder contains the frontend components for the dual-dashboard conversational AI assistants.

## Components:
- `ChatDrawer.tsx`: The Organizer AI Co-Pilot slide-over panel. Provides quick prompts ("Draft post-event email", "Summarize audience feedback", "Analyze drop-off topics") and full conversational guidance.
- `EventChatWidget.tsx`: The Attendee "Talk to the Transcript" floating Q&A widget on the Event Detail Hub. Allows attendees to ask questions answered strictly from the session transcript.
- `../../hooks/useChatStream.ts`: React hook managing Server-Sent Events (SSE) token streaming from `/api/v1/chat/stream`.
