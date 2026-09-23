# Background Workers & Task Processing (Member 2)

This folder contains the Celery task queue integration for offloading heavy speech-to-text and LangGraph pipeline execution from HTTP worker threads.

## Files:
- `celery_app.py`: Celery instance connected to Redis broker and result backend.
- `tasks.py`: Asynchronous task definition (`process_recording`) running the end-to-end pipeline in background processes.
