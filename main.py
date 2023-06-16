import re
import json
import uvicorn
import requests
from urllib.parse import urlparse
from threading import Thread, enumerate
from base64 import b64encode, b64decode
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, HTMLResponse, FileResponse, RedirectResponse, StreamingResponse



# 开始FastAPI及相关设置
app = FastAPI()
tscache = {}
header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
}

proxies = {
    'http': 'http://127.0.0.1:10809',
    'https': 'http://127.0.0.1:10809'
}

# 获取油管播放链接
async def getplayUrl(rid, baseurl):
    url = 'https://www.youtube.com/watch?v={}'.format(rid)
    r = requests.get(url=url, headers=header, verify=False, timeout=30, proxies=proxies)
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
    content = await getM3U8(url, baseurl)
    return content

async def getM3U8(url, baseurl):
    r = requests.get(url=url, headers=header, verify=False, timeout=30, proxies=proxies)
    m3u8str = ''
    tsurlList = []
    m3u8List = r.text.splitlines()
    for line in m3u8List:
        if not line.startswith('#'):
            if line.endswith('.ts'):
                tsurlList.append(line)
                append = '/proxymedia?url='
            else:
                append = '/proxym3u8?url='
            m3u8str = m3u8str + baseurl + append + b64encode(line.encode()).decode() + '\n'
        else:
            m3u8str = m3u8str + line + '\n'
    # 下载TS
    threadnum = 0
    if 'tsnum' in tscache:
        urlnum = tscache['tsnum']
    else:
        urlnum= 0
    for tsurl in tsurlList:
        for t in enumerate():
            if t.name.startswith('catchts'):
                threadnum += 1
        if threadnum >= 16:
            break
        # 油管为-2,其他碰到再说
        tsurlnum = int(re.findall(r"\d+(?:\.\d+)?", tsurl)[-2])
        if urlnum >= tsurlnum:
            continue
        thread = Thread(target=cachets, args=(tsurl,), name='catchts_{}'.format(tsurl))
        thread.daemon = True
        thread.start()
    return m3u8str.strip('\n')


def cachets(url):
    try:
        r = requests.get(url=url, headers=header, verify=False, timeout=30, proxies=proxies)
        content = r.content
    except:
        content = b''
    tscache[url] = content


def delcache(url):
    tsnum = int(re.findall(r"\d+(?:\.\d+)?", url)[-2])
    tscache['tsnum'] = tsnum
    keysList = list(tscache.keys())
    for key in keysList:
        if key == 'tsnum':
            continue
        if tsnum >= int(re.findall(r"\d+(?:\.\d+)?", key)[-2]):
            del tscache[key]


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
    keysList = list(tscache.keys())
    for key in keysList:
        if key == 'tsnum':
            tscache['tsnum'] = 0
        else:
            del tscache[key]
    baseurl = str(request.url).split('/live')[0]
    try:
        content = await getplayUrl(rid, baseurl)
    except:
        content = ''
    if content == '':
        return RedirectResponse(url='http://0.0.0.0/')
    return Response(content, headers={"Content-Type": "application/vnd.apple.mpegurl", "Content-Disposition": "attachment; filename=youtube.m3u8"})


# 代理油管M3u8
@app.get('/proxym3u8')
async def proxym3u8(url: str, request: Request):
    url = b64decode(url.encode()).decode()
    result = urlparse(str(request.url))
    baseurl = '{}://{}'.format(result.scheme, result.netloc)
    try:
        content = await getM3U8(url, baseurl)
    except:
        content = ''
    if content == '':
        return RedirectResponse(url='http://0.0.0.0/')
    return Response(content, headers={"Content-Type": "application/vnd.apple.mpegurl", "Content-Disposition": "attachment; filename=youtube.m3u8"})


# 代理油管切片
@app.get('/proxymedia')
async def proxymedia(url: str, request: Request):
    url = b64decode(url.encode()).decode()
    if url in tscache:
        content = tscache[url]
    else:
        cachets(url)
        content = tscache[url]
    delcache(url)
    return Response(content=content, media_type="video/mp2t")


if __name__ == '__main__':
    uvicorn.run(app='main:app', host="0.0.0.0", port=8251, reload=False)
