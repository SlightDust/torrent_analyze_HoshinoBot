import urllib
import re

debug = True

if debug:
    import sys, os
    _current_dir = os.path.dirname(__file__)
    if _current_dir not in sys.path:
        sys.path.insert(-1, _current_dir)
    import aiorequests
    import asyncio
else:
    from hoshino import Service, priv, aiorequests

def hum_convert(value):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for i in range(len(units)):
        if (value / size) < 1:
            return "%.2f%s" % (value, units[i])
        value = value / size

def is_torrent(torrent_hash):
    # 本来就是个hash
    if len(torrent_hash) in [32, 40]:
        magnet_url = f"magnet:?xt=urn:btih:{hash[0]}"
        return True, magnet_url
    # 是磁链
    hash = re.findall(r"magnet:\?xt=urn:btih:(\w+)", torrent_hash)
    if hash and len(hash[0]) in [32, 40]:
        return True, torrent_hash
    else:
        return False, None

async def analyze_torrent(torrent_url):
    flag, torrent_url = is_torrent(torrent_url)
    if not flag:
        msg = "这不是一个磁链或种子hash"
    else:
        # url编码
        url = urllib.parse.quote(torrent_url)
        url = f"https://whatslink.info/api/v1/link?url={url}"
        # print(url)
        ares = await aiorequests.get(url, timeout=5)
        res = await ares.json()
        # {'error': '', 'type': 'FILE', 'file_type': 'video', 'name': '[ANi] ATRI -My Dear Moments-（僅限港澳台） - 09 [1080P][Bilibili][WEB-DL][AAC AVC][CHT CHS].mp4', 'size': 329259410, 'count': 1, 'screenshots': [{'time': 0, 'screenshot': 'https://whatslink.info/image/1d694dc833f4511b1f7957df388f042d'}, {'time': 0, 'screenshot': 'https://whatslink.info/image/f2fa88a20e38f3ad772dbd7ed1663ee2'}, {'time': 0, 'screenshot': 'https://whatslink.info/image/f3eb18fd111b2eb41299f6110fa5bbec'}, {'time': 0, 'screenshot': 'https://whatslink.info/image/d81618c94ecbb2c5d7f11bd869ea1764'}, {'time': 0, 'screenshot': 'https://whatslink.info/image/16ca5f1ed24841b2086dda33b1600646'}]}
        print(res)
        if res['error'] == '':
            msg = f"文件类型：{res['type']}-{res['file_type']}\n种子名称: {res['name']}\n总大小: {hum_convert(res['size'])}\n文件总数：{res['count']}\n"
            if len(res['screenshots']) > 0:
                msg += "种子截图：\n"
                for i in res['screenshots'][:3]:
                    msg += f"  {i['screenshot']}\n"
        elif res['error'] == 'quota_limited':
            msg = "分析失败: 请求过于频繁，请稍后再试"
        else:
            msg = f"分析失败：{res['error']}"
    print(msg)
    return msg

# 执行异步run
if __name__ == '__main__':
    if debug:
        loop = asyncio.get_event_loop()
        url = "magnet:?xt=urn:btih:4d78216de4b71a35d52ff37977378d5f448cc31b"
        loop.run_until_complete(analyze_torrent(url))