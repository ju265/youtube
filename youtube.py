import os
import re
import json
import requests


class YouTuBe():
    def get_real_url(self, rid):
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
            "Connection": "keep-alive"
        }
        url = 'https://www.youtube.com/watch?v={}'.format(rid)

        r = requests.get(url=url, headers=header, timeout=30, verify=False)
        jostr_re = re.compile('var ytInitialPlayerResponse =(.*?});')
        jostr = jostr_re.findall(r.text)
        if not jostr:
            return ''
        jo = json.loads(jostr[0])
        if 'streamingData' in jo and 'hlsManifestUrl' in jo['streamingData']:
            if type(jo['streamingData']['hlsManifestUrl']) is str:
                url = jo['streamingData']['hlsManifestUrl']
            elif type(jo['streamingData']['hlsManifestUrl']) is list:
                url = jo['streamingData']['hlsManifestUrl'][0]
            else:
                return ''
            r = requests.get(url, headers=header, timeout=30, verify=False, allow_redirects=False)
            m3u8List = r.text.strip('\n').split('\n')
            url = m3u8List[-1]
        else:
            return ''
        return url
