import requests
from flask import current_app

def get_instagram_feed():
    # Instagram API integration
    api_key = current_app.config['INSTAGRAM_API_KEY']
    endpoint = f"https://graph.instagram.com/me/media?fields=id,caption,media_type,media_url,permalink&access_token={api_key}"
    response = requests.get(endpoint)
    return response.json()

def get_youtube_videos():
    # YouTube API integration
    api_key = current_app.config['YOUTUBE_API_KEY']
    channel_id = current_app.config['YOUTUBE_CHANNEL_ID']
    endpoint = f"https://www.googleapis.com/youtube/v3/search?key={api_key}&channelId={channel_id}&part=snippet,id&order=date&maxResults=20"
    response = requests.get(endpoint)
    return response.json() 