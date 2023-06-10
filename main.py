import re
import json
import uvicorn
import requests
from urllib.parse import urlparse
from base64 import b64encode, b64decode
from fastapi import FastAPI, Request
from fastapi.responses import Response, HTMLResponse, FileResponse, RedirectResponse, StreamingResponse


header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
}


# 获取油管播放链接
def getplayUrl(rid, baseurl):
    url = 'https://www.youtube.com/watch?v={}'.format(rid)
    r = requests.get(url=url, headers=header, verify=False, timeout=30)
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
    else:
        return ''
    return getM3U8(url, baseurl)


def getM3U8(url, baseurl):
    r = requests.get(url, headers=header, stream=True, verify=False, timeout=30)
    m3u8str = ''
    for line in r.iter_lines(8192):
        if len(line) > 0 and not line.startswith(b'#'):
            if line.endswith(b'.ts'):
                append = '/proxymedia?url='
            else:
                append = '/proxym3u8?url='
            line = b64encode(line).decode()
            m3u8str = m3u8str + baseurl + append  + line + '\n'
        else:
            line = line.decode()
            m3u8str = m3u8str + line + '\n'
    r.close()
    return m3u8str.strip('\n')


# 获取chunk
def getChunk(streamable):
    with streamable as stream:
        stream.raise_for_status()
        try:
            for chunk in stream.iter_content(chunk_size=1024*1024):
                if chunk is None:
                    stream.close()
                    return
                yield chunk
        except:
            stream.close()
            return


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


# 获取油管M3u8
@app.get('/live')
async def live(rid: str, request: Request):
    baseurl = str(request.url).split('/live')[0]
    content = getplayUrl(rid, baseurl)
    if content == '':
        return RedirectResponse(url='http://0.0.0.0/')
    return Response(content, headers={"Content-Type": "application/vnd.apple.mpegurl", "Content-Disposition": "attachment; filename=youtube.m3u8"})


# 代理油管M3u8
@app.get('/proxym3u8')
async def proxym3u8(url: str, request: Request):
    url = b64decode(url.encode()).decode()
    result = urlparse(str(request.url))
    baseurl = '{}://{}'.format(result.scheme, result.netloc)
    content = getM3U8(url, baseurl)
    if content == '':
        return RedirectResponse(url='http://0.0.0.0/')
    return Response(content, headers={"Content-Type": "application/vnd.apple.mpegurl", "Content-Disposition": "attachment; filename=youtube.m3u8"})


# 代理油管切片
@app.get('/proxymedia')
async def proxymedia(url: str, request: Request):
    url = b64decode(url.encode()).decode()
    selfheader = dict(request.headers)
    responheader = {}
    for key in selfheader:
        if key.lower() in ['user-agent', 'host']:
            continue
        responheader[key] = selfheader[key]
        r = requests.get(url, headers=responheader, stream=True, verify=False, timeout=30)
    try:
        contentType = r.headers['content-type']
        status_code = r.status_code
        for key in r.headers:
            if key.lower() in ['connection', 'transfer-encoding']:
                continue
            if contentType.lower() in ['application/vnd.apple.mpegurl', 'application/x-mpegurl']:
                if key.lower() in ['content-length', 'content-range', 'accept-ranges']:
                    continue
            responheader[key] = r.headers[key]
        return StreamingResponse(getChunk(r), status_code=status_code, headers=responheader)
    except:
        r.close()
        pass


if __name__ == '__main__':
    uvicorn.run(app='main:app', host="0.0.0.0", port=8251, reload=False)
