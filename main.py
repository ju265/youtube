import re
import json
import uvicorn
import requests
from io import BytesIO
from base64 import b64decode, b64encode
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse


header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
}


# 获取油管播放链接
def getplayUrl(rid):
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


# 获取M3U8
def getM3u8(url, baseurl):
        m3u8List = []
        proxyhead = baseurl + '/proxy?ts_url='
        try:
            r = requests.get(url, headers=header, stream=True, allow_redirects=False, verify=False)
            if 'Content-Type' in r.headers and 'video' in r.headers['Content-Type']:
                r.close()
                url = '/proxy?ts_url=' + b64encode(url.encode("utf-8")).decode("utf-8")
                return url, 'False'
            elif 'Location' in r.headers and '#EXTM3U' not in r.text:
                r.close()
                url = r.headers['Location']
                r = requests.get(url, headers=header, timeout=30, stream=True, allow_redirects=False, verify=False)
            start = 0
            posD = -1
            posDISList = []
            for line in r.iter_lines(8096):
                line = line.decode('utf-8', 'ignore')
                EXK_str = ''
                if len(line) > 0 and "EXT-X-KEY" in line:
                    EXK_str = line
                    line = re.search(r'URI=(.*)', line).group(1).replace('"', '').strip().split(',')[0]
                    oURI = line
                if len(line) > 0 and not line.startswith('#'):
                    if line.find(".m3u") != -1 and not line.find(".ts") != -1:
                        m3u8_url = line
                        return getM3u8(m3u8_url, baseurl)
                    if not line.startswith('http'):
                        if line.startswith('/'):
                            line = url[:url.index('/', 8)] + line
                        else:
                            line = url[:url.rindex('/') + 1] + line
                    line = proxyhead + b64encode(line.encode("utf-8")).decode("utf-8")
                if EXK_str != '':
                    line = EXK_str.replace(oURI, line)
                m3u8List.append(line)
                if m3u8List[posD + 1:].count('#EXT-X-DISCONTINUITY') != 0:
                    posD = m3u8List.index('#EXT-X-DISCONTINUITY', posD + 1)
                    if posD > 0 and not m3u8List[posD - 1].startswith('#'):
                        posDISList.append(posD)
            if len(posDISList) > 0:
                for posDIS in posDISList:
                    if posDIS > 0:
                        if start == 0:
                            start = posDIS
                            end = -1
                            continue
                        if end == -1:
                            end = posDIS + 1
            if start != 0 and end != -1:
                del m3u8List[start:end]
                start = 0
            m3u8str = "\n".join(m3u8List).strip('\n')
            return m3u8str
        except:
            return ''
        finally:
            try:
                r.close()
            except:
                pass


# 开始FastAPI及相关设置
app = FastAPI()


# 提供 index.html 文件
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html")


# 设置网页图标
@app.get("/favicon.ico")
async def favicon():
    return FileResponse("templates/favicon.ico")

# 获取油管M3u
@app.get('/live')
async def live(rid: str, request: Request):
    baseurl = '{}://{}'.format(request.url.scheme, request.url.netloc)
    playurl = getplayUrl(rid)
    if playurl == '':
        return RedirectResponse(url='http://0.0.0.0/')
    playcxt = getM3u8(playurl, baseurl)
    return StreamingResponse(BytesIO(playcxt.encode("utf-8")), media_type="audio/x-mpegurl", headers={"Content-Disposition": "attachment; filename=proxied.m3u8"})


@app.get('/proxy')
async def proxy(ts_url: str, request: Request):
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
    }
    headers = {}
    url = b64decode(ts_url.encode()).decode()
    for key, value in request.headers.items():
        if key.lower() in ['user-agent', 'host']:
            continue
        header[key] = value
        headers[key] = value
    try:
        r = requests.get(url=url, headers=header, stream=True)
        for key in r.headers:
            if key.lower() in ['user-agent', 'host']:
                continue
            headers[key] = r.headers[key]
        if 'Range' in headers:
            status_code = 206
        else:
            status_code = 200
        return StreamingResponse(getChunk(r), status_code=status_code, headers=headers)
    except:
        pass
    finally:
        r.close()


def getChunk(streamable):
    with streamable as stream:
        stream.raise_for_status()
        try:
            for chunk in stream.iter_content(chunk_size=40960):
                if chunk is None:
                    stream.close()
                    return
                yield chunk
        except:
            return


if __name__ == '__main__':
    uvicorn.run(app='main:app', host="0.0.0.0", port=8251, reload=False)
