import re
import json
import httpx
import uvicorn
import asyncio
from urllib.parse import urlparse
from base64 import b64encode, b64decode
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, HTMLResponse, FileResponse, RedirectResponse, StreamingResponse



# 开始FastAPI及相关设置
app = FastAPI()
tscache = {}
header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
}
# 获取油管播放链接
async def getplayUrl(rid, baseurl):
    url = 'https://www.youtube.com/watch?v={}'.format(rid)
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
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
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
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
    # 异步下载TS
    tasks = []
    for url in tsurlList:
        if url not in tscache:
            tasks.append(cachets(url))
    await asyncio.gather(*tasks)
    return m3u8str.strip('\n')


async def cachets(url):
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        content = r.content
    tscache[url] = content


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
    try:
        content = await getplayUrl(rid, baseurl)
    except:
        pass
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
        pass
    if content == '':
        return RedirectResponse(url='http://0.0.0.0/')
    return Response(content, headers={"Content-Type": "application/vnd.apple.mpegurl", "Content-Disposition": "attachment; filename=youtube.m3u8"})


# 代理油管切片
@app.get('/proxymedia')
async def proxymedia(url: str, request: Request):
    url = b64decode(url.encode()).decode()
    if url in tscache:
        content = tscache[url]
        del tscache[url]
        return Response(content=content, media_type="video/mp2t")
    else:
        raise HTTPException(status_code=404, detail="404 Not Found")


if __name__ == '__main__':
    uvicorn.run(app='main:app', host="0.0.0.0", port=8251, reload=False)
