import re
import json
import uvicorn
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse


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
    else:
        return ''
    return url


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
async def live(rid: str):
    playurl = getplayUrl(rid)
    if playurl == '':
        return RedirectResponse(url='http://0.0.0.0/')
    return RedirectResponse(url=playurl)



if __name__ == '__main__':
    uvicorn.run(app='main:app', host="0.0.0.0", port=8251, reload=False)
