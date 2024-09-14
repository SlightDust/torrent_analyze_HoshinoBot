import urllib
import re
import json
import traceback
import os
import sys
import asyncio

from requests.adapters import ConnectTimeoutError
from requests.exceptions import SSLError

_current_dir = os.path.dirname(__file__)
cache_path = os.path.join(_current_dir, "torrent_info_cache.json")

debug = False

if debug:
    if _current_dir not in sys.path:
        sys.path.insert(-1, _current_dir)
    import aiorequests
else:
    from hoshino import Service, priv, aiorequests
    sv = Service(
        name = 'torrent_analyze',  #,  #功能名
        use_priv = priv.NORMAL, #使用权限   
        manage_priv = priv.ADMIN, #管理权限
        visible = True, #False隐藏
        enable_on_default = True, #是否默认启用
    )
    @sv.on_prefix(("验车","种子分析","种子信息","种子详情"))
    async def check_torrent(bot, ev):
        txt = ev.message.extract_plain_text().strip()
        if not txt:
            await bot.send(ev, "请输入种子链接或hash")
            return
        try:
            msg = await analyze_torrent(txt)
            await bot.send(ev, msg)
        except Exception as e:
            await bot.send(ev, f"未知错误：{traceback.format_exc()}")


# 初次启动时，检查torrent_info_cache.json是否存在，不存在则创建
if not os.path.exists(cache_path):
    with open(cache_path, "w") as f:
        f.write("{}")

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
        magnet_url = f"magnet:?xt=urn:btih:{torrent_hash}"
        return True, magnet_url, torrent_hash
    
    # 是磁链
    hash = re.findall(r"magnet:\?xt=urn:btih:(\w+)", torrent_hash)
    if hash and len(hash[0]) in [32, 40]:
        magnet_url = torrent_hash
        torrent_hash = hash[0]
        return True, magnet_url, torrent_hash
    else:
        return False, None, None

async def check_cache(torrent_hash):
    '''
    根据种子hash检查缓存，命中则返回缓存结果，未命中则返回None
    '''
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    if torrent_hash in cache:
        return cache[torrent_hash]
    else:
        return None

async def write_cache(torrent_hash, res):
    '''
    将网站返回结果原封不动写入缓存
    '''
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    cache[torrent_hash] = res
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)

async def analyze_torrent(torrent_url):
    flag, magnet_url, torrent_hash = is_torrent(torrent_url)
    if not flag:
        msg = "这不是一个磁链或种子hash"
        return msg
    else:
        # 先检查缓存
        cache_res = await check_cache(torrent_hash)
        if cache_res: # 命中缓存
            res = cache_res
            msg = f"种子哈希: {torrent_hash}\n"
            msg += f"文件类型：{res['type']}-{res['file_type']}\n"
            msg += f"种子名称: {res['name']}\n"
            msg += f"总大小: {hum_convert(res['size'])}\n"
            msg += f"文件总数：{res['count']}"
            return msg.strip()
        else: # 未命中缓存
            # url编码
            baseurl = "https://whatslink.info"
            api_path = "/api/v1/link"
            url = urllib.parse.quote(magnet_url)
            url = f"{baseurl}{api_path}?url={url}"
            # 循环20次，直到成功或达到最大次数
            ok = False
            for i in range(20):
                print(f"第{i+1}次请求")
                try:
                    ares = await aiorequests.get(url, timeout=10)
                    res = await ares.json()
                    await asyncio.sleep(3)
                    if res['error'] == '':
                        # 缓存结果
                        await write_cache(torrent_hash, res)
                        ok = True
                        break
                except ConnectTimeoutError:
                    msg = f"连接{baseurl}失败，请稍后再试。" 
                    return msg 
                except SSLError:
                    msg = f"连接{baseurl}失败，请稍后再试。"
                    return msg
                except Exception as e:
                    msg = f"分析失败：{e}"
                    return msg
            if not ok:
                msg = f"分析失败，请稍后再试。"
                return msg
            else:
                msg = f"种子哈希: {torrent_hash}\n"
                msg += f"文件类型：{res['type']}-{res['file_type']}\n"
                msg += f"种子名称: {res['name']}\n"
                msg += f"总大小: {hum_convert(res['size'])}\n"
                msg += f"文件总数：{res['count']}"
                # if len(res['screenshots']) > 0:
                #     msg += "种子截图：\n"
                #     for i in res['screenshots'][:3]:
                #         msg += f"  {i['screenshot']}\n"
            return msg.strip()


# debug
if __name__ == '__main__':
    if debug:
        loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        url = "ec809a3d681c2dda1bc1ae8feb84c4b8077896b2"
        print(loop.run_until_complete(analyze_torrent(url)))