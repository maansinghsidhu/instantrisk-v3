"""
Example Voice Interface Client

This script demonstrates how to interact with the InstantRisk Voice Interface API
from a client application.

Usage:
    python example_voice_client.py --audio command.wav --token YOUR_JWT_TOKEN
"""

import argparse
import requests
import json
import sys
from pathlib import Path


class VoiceInterfaceClient:
    """Client for InstantRisk Voice Interface API."""

    def __init__(self, base_url: str, token: str):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the API (e.g., http://localhost:8200)
            token: JWT authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}'
        }

    def transcribe_audio(self, audio_path: str) -> dict:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to audio file

        Returns:
            dict: Transcription result with text, language, confidence, duration
        """
        url = f'{self.base_url}/api/v1/voice/transcribe'

        with open(audio_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files, headers=self.headers)

        response.raise_for_status()
        return response.json()

    def execute_command(self, audio_path: str) -> dict:
        """
        Execute a voice command from an audio file.

        Args:
            audio_path: Path to audio file with voice command

        Returns:
            dict: Command execution result with success, data, summary
        """
        url = f'{self.base_url}/api/v1/voice/command'

        with open(audio_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files, headers=self.headers)

        response.raise_for_status()
        return response.json()

    def get_supported_commands(self) -> dict:
        """
        Get list of supported voice commands.

        Returns:
            dict: List of supported commands with examples
        """
        url = f'{self.base_url}/api/v1/voice/supported-commands'
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def check_health(self) -> dict:
        """
        Check voice interface health status.

        Returns:
            dict: Health status information
        """
        url = f'{self.base_url}/api/v1/voice/health'
        response = requests.get(url)  # No auth required
        response.raise_for_status()
        return response.json()


def print_json(data: dict, indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='InstantRisk Voice Interface Client Example'
    )
    parser.add_argument(
        '--base-url',
        default='http://localhost:8200',
        help='Base URL of the API (default: http://localhost:8200)'
    )
    parser.add_argument(
        '--token',
        help='JWT authentication token (required for most operations)'
    )
    parser.add_argument(
        '--audio',
        help='Path to audio file for transcription or command execution'
    )
    parser.add_argument(
        '--mode',
        choices=['transcribe', 'command', 'commands', 'health'],
        default='command',
        help='Operation mode (default: command)'
    )

    args = parser.parse_args()

    # Create client
    client = VoiceInterfaceClient(args.base_url, args.token or '')

    try:
        if args.mode == 'health':
            # Health check (no auth required)
            print("Checking voice interface health...\n")
            result = client.check_health()
            print_json(result)

        elif args.mode == 'commands':
            # List supported commands
            if not args.token:
                print("Error: --token required for this operation")
                sys.exit(1)

            print("Fetching supported commands...\n")
            result = client.get_supported_commands()

            print(f"Found {result['count']} supported commands:\n")
            for cmd in result['commands']:
                print(f"Command: {cmd['command']}")
                print(f"  Description: {cmd['description']}")
                print(f"  Parameters: {cmd['parameters']}")
                print(f"  Examples:")
                for example in cmd['examples']:
                    print(f"    - {example}")
                print()

        elif args.mode == 'transcribe':
            # Transcribe audio
            if not args.token:
                print("Error: --token required for this operation")
                sys.exit(1)
            if not args.audio:
                print("Error: --audio required for this operation")
                sys.exit(1)
            if not Path(args.audio).exists():
                print(f"Error: Audio file not found: {args.audio}")
                sys.exit(1)

            print(f"Transcribing audio: {args.audio}\n")
            result = client.transcribe_audio(args.audio)

            print("Transcription Result:")
            print(f"  Text: {result['text']}")
            print(f"  Language: {result['language']}")
            print(f"  Confidence: {result['confidence']:.2%}")
            print(f"  Duration: {result['duration']:.2f}s")

        elif args.mode == 'command':
            # Execute voice command
            if not args.token:
                print("Error: --token required for this operation")
                sys.exit(1)
            if not args.audio:
                print("Error: --audio required for this operation")
                sys.exit(1)
            if not Path(args.audio).exists():
                print(f"Error: Audio file not found: {args.audio}")
                sys.exit(1)

            print(f"Executing voice command from: {args.audio}\n")
            result = client.execute_command(args.audio)

            print("Command Execution Result:")
            print(f"  Success: {result['success']}")
            if result.get('command'):
                print(f"  Command: {result['command']}")
            print(f"  Summary: {result['summary']}")

            if result.get('data'):
                print("\n  Data:")
                print_json(result['data'], indent=4)

            if result.get('transcription'):
                print("\n  Transcription:")
                print(f"    Text: {result['transcription']['text']}")
                print(f"    Confidence: {result['transcription']['confidence']:.2%}")

    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP Error: {e}")
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Error Details: {error_detail.get('detail', 'No details available')}")
            except:
                print(f"Response: {e.response.text}")
        sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"\nRequest Error: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
