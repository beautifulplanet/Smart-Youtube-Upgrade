# Privacy Policy - YouTube Safety Inspector

**Last updated:** February 13, 2026

## Data Collection

YouTube Safety Inspector does **not** collect, store, or transmit any personal data.

## What the extension accesses

- **YouTube video metadata**: Title, description, channel name, and comments are read from the YouTube page you are viewing. This data is used solely for safety analysis and is not stored or transmitted to third parties.
- **YouTube transcripts**: Video transcripts are fetched from YouTube's transcript API for safety analysis only.
- **Extension settings**: Your preferences (sensitivity levels, trusted channels, toggle states) are stored locally in your browser using Chrome's storage API. These never leave your device.

## API Communication

When analysis is performed, video metadata may be sent to the YouTube Safety Inspector backend API for processing. This API:
- Does not log or store video IDs or metadata beyond the duration of the request
- Does not associate requests with user identities
- Does not use cookies or tracking mechanisms
- Does not share data with third parties

## Third-Party Services

- **YouTube Data API**: Used to fetch video metadata and comments when a YouTube API key is configured. Subject to [Google's Privacy Policy](https://policies.google.com/privacy).

## Local Storage

The extension stores the following data locally on your device:
- User preferences and settings
- Trusted channel list
- Daily rate limit counter (resets daily)
- Cached analysis results (optional, configurable)

No data is transmitted externally except for API analysis requests as described above.

## Changes

This privacy policy may be updated. Changes will be noted in the extension's changelog.

## Contact

For privacy questions, open an issue on the project's GitHub repository.
