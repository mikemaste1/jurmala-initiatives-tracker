import argparse
import os
import requests
import climage
from google import genai
from PIL import Image
import tempfile

def main():
    parser = argparse.ArgumentParser(description="Download a captcha image, show it in console, and solve it with Gemini API.")
    parser.add_argument("uri", help="The URI of the captcha image to download.")
    parser.add_argument("--api-key", help="Google Gemini API key. Can also be set via GEMINI_API_KEY environment variable.", default=None)
    
    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Gemini API key is required. Pass via --api-key or GEMINI_API_KEY environment variable.")
        return

    # Download image
    print(f"Downloading image from {args.uri}...")
    try:
        response = requests.get(args.uri, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to download image: {e}")
        return

    # Save to temp file
    temp_img_fd, temp_img_path = tempfile.mkstemp(suffix=".png")
    os.close(temp_img_fd)
    
    try:
        with open(temp_img_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Show image in console using climage
        print("\nDownloaded Captcha Image:")
        try:
            converted = climage.convert(temp_img_path, is_unicode=True, width=50)
            print(converted)
        except Exception as e:
            print(f"Could not display image in terminal: {e}")

        # Send to Gemini
        print("Sending image to Gemini API for recognition...")
        client = genai.Client(api_key=api_key)
        
        # Open PIL Image to pass to SDK
        img = Image.open(temp_img_path)
        
        prompt = "Read the 5 captcha characters in this image. Respond ONLY with the 5 characters."
        
        # Use gemini-2.5-flash for vision tasks
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img]
        )
        
        print("\n" + "="*30)
        print("Recognized Characters:", response.text.strip())
        print("="*30 + "\n")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

if __name__ == "__main__":
    main()
