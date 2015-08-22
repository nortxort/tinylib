"""
Provides functions to search the API of youtube, soundcloud, urbandictionary, worldweatheronline , ip-api and api.icndb
Requires isodate and requests to be installed.
"""
import requests
import isodate


def make_api_request(api_url):
    """
    Makes GET requests to a given API url.

    :param api_url: The url str to the API.
    :return: dict['json', 'cookies', 'headers'] or None on error.
    """

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Referer': 'http://tinychat.com/embed/Tinychat-11.1-1.0.0.0640.swf?version=1.0.0.0640'
    }

    response = requests.get(api_url, timeout=20, headers=headers)
    try:
        content = response.json()
    except ValueError:
        content = None

    return {'json': content, 'cookies': response.cookies, 'headers': response.headers}


def youtube_search(search):
    """
    Searches the youtube API for a youtube video matching the search term.

    A json response of ~50 possible items matching the search term will be presented.
    Each video_id will then be checked by youtube_time() until a candidate has been found
    and the resulting dict can be returned.

    :param search: The search term str to search for.
    :return: dict['type=youtube', 'video_id', 'int(video_time)', 'video_title'] or None on error.
    """

    if str(search).strip():
        youtube_search_url = 'https://www.googleapis.com/youtube/v3/search?' \
                             'type=video&key=AIzaSyCPQe4gGZuyVQ78zdqf9O5iEyfVLPaRwZg' \
                             '&maxResults=50&q=%s&part=snippet' % search

        response = make_api_request(youtube_search_url)

        if response['json'] is not None:
            try:
                for item in response['json']['items']:
                    video_id = item['id']['videoId']
                    video_title = item['snippet']['title'].encode('ascii', 'ignore')

                    video_time = youtube_time(video_id)
                    if video_time is not None:
                        return {'type': 'youtube', 'video_id': video_id,
                                'video_time': video_time['video_time'], 'video_title': video_title}
            except KeyError:
                return None
    else:
        return None


def youtube_search_list(search, results=10):
    """
    Searches the API of youtube for videos matching the search term.

    Instead of returning only one video matching the search term, we return a list of candidates.

    :param search: The search term str to search for.
    :param results: int determines how many results we would like on our list
    :return: list[dict{'type=youtube', 'video_id', 'int(video_time)', 'video_title'}] or None on error.
    """
    if str(search).strip():
        youtube_search_url = 'https://www.googleapis.com/youtube/v3/search?type=video' \
                             '&key=AIzaSyCPQe4gGZuyVQ78zdqf9O5iEyfVLPaRwZg' \
                             '&maxResults=50&q=%s&part=snippet' % search

        response = make_api_request(youtube_search_url)
        if response['json'] is not None:
            media_list = []
            try:
                i = 0
                for item in response['json']['items']:
                    if i >= results:
                        return media_list
                    else:
                        video_id = item['id']['videoId']
                        video_title = item['snippet']['title'].encode('ascii', 'ignore')

                        video_time = youtube_time(video_id)
                        if video_time is not None:
                            media_info = {'type': 'youtube', 'video_id': video_id,
                                          'video_time': video_time['video_time'], 'video_title': video_title}
                            media_list.append(media_info)
                            i += 1
            except KeyError:
                return None
    else:
        return None


def youtube_time(video_id, check=True):
    """
    Youtube helper function to get the video time for a given video id.

    Checks a youtube video id to see if the video is blocked or allowed in the following countries:
    USA, DENMARK, POLAND, UNITED KINGDOM and CANADA. If a video is blocked in one of the countries, None is returned.
    If a video is NOT allowed in ONE of the countries, None is returned else the video time will be returned.

    :param check: bool True = checks region restriction. False = no check will be done
    :param video_id: The youtube video id str to check.
    :return: dict['video_time', 'video_title'] or None
    """

    youtube_details_url = 'https://www.googleapis.com/youtube/v3/videos?' \
                          'id=%s&key=AIzaSyCPQe4gGZuyVQ78zdqf9O5iEyfVLPaRwZg&part=contentDetails,snippet' % video_id

    response = make_api_request(youtube_details_url)

    if response['json'] is not None:
        try:
            contentdetails = response['json']['items'][0]['contentDetails']
            if check:
                if 'regionRestriction' in contentdetails:
                    if 'blocked' in contentdetails['regionRestriction']:
                        if ('US' or 'DK' or 'PL' or 'UK' or 'CA') in contentdetails['regionRestriction']['blocked']:
                            return None
                    if 'allowed' in contentdetails['regionRestriction']:
                        if ('US' or 'DK' or 'PL' or 'UK' or 'CA') not in contentdetails['regionRestriction']['allowed']:
                            return None

            video_time = convert_to_millisecond(contentdetails['duration'])
            video_title = response['json']['items'][0]['snippet']['title'].encode('ascii', 'ignore')

            return {'video_time': video_time, 'video_title': video_title}
        except KeyError:
            return None


def convert_to_millisecond(duration):
    """
    Converts a ISO 8601 duration str to milliseconds.

    :param duration: The ISO 8601 duration str
    :return: int milliseconds
    """

    milli = isodate.parse_duration(duration)
    return int(milli.total_seconds() * 1000)


def soundcloud_search(search):
    """
    Searches soundcloud's API for a given search term.

    :param search: The search term str to search for.
    :return: dict['type=soundcloud', 'video_id', 'video_time', 'video_title'] or None on no match or error.
    """

    if str(search).strip():
        search_url = 'http://api.soundcloud.com/tracks.json?' \
                     'filter=streamable&order=hotness&q=%s&limit=25&client_id=4ce43a6430270a1eea977ff8357a25a3' % search

        response = make_api_request(search_url)

        if response['json'] is not None:
            try:
                track_id = response['json'][0]['id']
                track_time = response['json'][0]['duration']
                track_title = response['json'][0]['title'].encode('ascii', 'ignore')
                return {'type': 'soundcloud', 'video_id': track_id, 'video_time': track_time, 'video_title': track_title}
            except KeyError:
                return None
            except IndexError:
                return None
    else:
        return None


def urbandictionary_search(search):
    """
    Searches urbandictionary's API for a given search term.

    :param search: The search term str to search for.
    :return: defenition str or None on no match or error.
    """

    if str(search).strip():
        urban_api_url = 'http://api.urbandictionary.com/v0/define?term=%s' % search
        response = make_api_request(urban_api_url)

        if response:
            try:
                definition = response['json']['list'][0]['definition']
                return definition
            except KeyError:
                return None
            except IndexError:
                return None
    else:
        return None


def weather_search(city):
    """
    Searches worldweatheronline's API for weather data for a given city.
    You must have a working API key to be able to use this function.

    :param city: The city str to search for.
    :return: weather data str or None on no match or error.
    """

    if str(city).strip():
        api_key = '' # A working API key.
        if not api_key:
            return 'Missing api key.'
        else:
            weather_api_url = 'http://api.worldweatheronline.com/free/v2/weather.ashx?' \
                              'q=%s&format=json&key=%s' % (city, api_key)

            response = make_api_request(weather_api_url)

            if response['json'] is not None:
                try:
                    pressure = response['json']['data']['current_condition'][0]['pressure']
                    temp_c = response['json']['data']['current_condition'][0]['temp_C']
                    temp_f = response['json']['data']['current_condition'][0]['temp_F']
                    query = response['json']['data']['request'][0]['query']
                    result = query + '. Tempature: ' + temp_c + 'C (' + temp_f + 'F) Pressure: ' + pressure + '  millibars'
                    return result
                except KeyError:
                    return None
                except IndexError:
                    return None
    else:
        return None


def whois(ip):
    """
    Searches ip-api for information about a given IP.

    :param ip: The ip str to search for.
    :return: information str or None on error.
    """

    if str(ip).strip():
        url = 'http://ip-api.com/json/%s' % ip
        json_data = make_api_request(url)
        try:
            city = json_data['json']['city']
            country = json_data['json']['country']
            isp = json_data['json']['isp']
            org = json_data['json']['org']
            region = json_data['json']['regionName']
            zipcode = json_data['json']['zip']
            info = country + ', ' + city + ', ' + region + ', Zipcode: ' + zipcode + '  Isp: ' + isp + '/' + org
            return info
        except KeyError:
            return None
    else:
        return None


def chuck_norris():
    """
    Finds a random Chuck Norris joke/quote.

    :return: joke str or None on failure.
    """

    url = 'http://api.icndb.com/jokes/random/?escape=javascript'
    json_data = make_api_request(url)
    if json_data['json']['type'] == 'success':
        joke = json_data['json']['value']['joke'].decode('string_escape')
        return joke
    else:
        return None
