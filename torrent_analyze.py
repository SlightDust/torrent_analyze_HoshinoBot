import urllib
import re
import json
import traceback
import os
import sys
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import base64
import httpx

from requests.adapters import ConnectTimeoutError
from requests.exceptions import SSLError

font_size = 24 # 字体大小
font_name = "SourceHanSerifSC-Light.otf" #SourceHanSansSC-Regular.otf是粗体

_current_dir = os.path.dirname(__file__)
cache_path = os.path.join(_current_dir, "torrent_info_cache.json")
font_path = os.path.join(_current_dir, font_name) 
group_config_path = os.path.join(_current_dir, "group_config.json")

debug = False

help_msg = f'''[验车 磁链] 查询磁链信息
[set验车(高斯|图片)(开|关)(0~10)] 修改本群验车参数(仅管理员可用)
set验车高斯开10 返回图片类型的磁链信息里的图片进行高斯模糊10
set验车图片开 返回图片类型的磁链信息
'''.strip()

if debug:
    if _current_dir not in sys.path:
        sys.path.insert(-1, _current_dir)
    import aiorequests
    class util:
        def filt_message(msg):
            return msg
else:
    from hoshino import Service, priv, util, aiorequests
    sv = Service(
        name = 'torrent_analyze',  #,  #功能名
        use_priv = priv.NORMAL, #使用权限   
        manage_priv = priv.ADMIN, #管理权限
        visible = True, #False隐藏
        enable_on_default = True, #是否默认启用
        help_=help_msg
    )

    @sv.on_fullmatch('验车帮助')
    async def torrent_help(bot, ev):
        try:
            await bot.send(ev, help_msg)
        except Exception as e:
            traceback.print_exc()
            await bot.send(ev, f"未知错误：请检查控制台")

    @sv.on_rex(re.compile(r'^set验车(高斯|图片)(开|关)([0-9]|10)?$'))
    async def set_torrent(bot, ev):
        try:
            match = ev['match']
            gid = str(ev.group_id)
            if not priv.check_priv(ev, priv.ADMIN):
                await bot.send(ev, '更改群设置仅限管理员操作', at_sender=True)
                return
            if await write_group_config(gid,match):
                msg = f'本群:{gid} 设置:{match[1]} 为 {match[2]}'
                if match[3]:
                    msg += f' 参数:{match[3]}'
            else:
                msg = '群设置修改失败'
            await bot.send(ev, msg)
        except Exception as e:
            traceback.print_exc()
            await bot.send(ev, f"未知错误：请检查控制台")
        
    @sv.on_prefix(("验车","种子分析","种子信息","种子详情"))
    async def check_torrent(bot, ev):
        try:
            txt = ev.message.extract_plain_text().strip()
            gid = str(ev.group_id)
            if not txt:
                await bot.send(ev, "请输入种子链接或hash")
                return
            msg = await analyze_torrent(txt,gid)
            await bot.send(ev, msg)
        except Exception as e:
            traceback.print_exc()
            await bot.send(ev, f"未知错误：请检查控制台")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Referer': 'https://whatslink.info/',
    'Cache-Control': 'no-cache'
}

# 初次启动时，检查torrent_info_cache.json是否存在，不存在则创建
if not os.path.exists(cache_path):
    with open(cache_path, "w") as f:
        f.write("{}")

if not os.path.exists(group_config_path):
    with open(group_config_path, "w") as f:
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

async def check_group_config(gid):
    '''
    返回群设置
    '''
    with open(group_config_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    return cache.get(gid,{})

async def write_group_config(gid, match):
    '''
    修改群设置
    '''
    try:
        config_name = match[1]
        config_signal = match[2]
        config_set = match[3]

        key = config_name
        value = True if config_signal == '开' else False

        if key == '高斯':
            key = 'blur_radius'
            value = int(config_set or 10) if value else 0
        else:
            key = 'image_set'

        with open(group_config_path, "r", encoding="utf-8") as f:
            cache = json.load(f)

        print(f"Before update: {cache}")  # 调试信息

        if gid not in cache:
            cache[gid] = {}

        # 使用 update 更新配置项
        cache[gid].update({key: value})

        print(f"After update: {cache}")  # 调试信息

        with open(group_config_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        traceback.print_exc()
        return False

async def image_to_base64(pil_image):
    img_buffer = BytesIO()
    pil_image.save(img_buffer, format='JPEG')
    byte_data = img_buffer.getvalue()
    base64_str = f'base64://{base64.b64encode(byte_data).decode()}'
    return f'[CQ:image,file={base64_str}]'

def create_image_from_text(text, font_size=font_size, line_spacing=10, margin=20):
    # 加载字体
    font = ImageFont.truetype(font_path, size=font_size)
    
    # 创建临时图像以计算文本大小
    temp_image = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(temp_image)
    
    # 将文本分行
    lines = text.split('\n')
    
    # 计算每行的宽度和高度
    max_width = 0
    total_height = 0
    for line in lines:
        line_width, line_height = draw.textsize(line, font=font)
        max_width = max(max_width, line_width)
        total_height += line_height + line_spacing
    
    # 给图像加上边距
    img_width = max_width + 2 * margin
    img_height = total_height + 2 * margin
    
    # 创建适应文本大小的图像
    image = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # 绘制文本
    y = margin
    for line in lines:
        draw.text((margin, y), line, fill=(0, 0, 0), font=font)
        y += font.getsize(line)[1] + line_spacing
    
    return image

async def fetch_image_with_blur(url, blur_radius=5):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        print(response.headers["Content-Type"])
        # 检查响应状态码和内容类型
        if response.status_code == 200 and "image" in response.headers["Content-Type"]:
            img_data = response.content
            try:
                image = Image.open(BytesIO(img_data))
                # 应用高斯模糊处理
                if blur_radius:
                    blurred_image = image.filter(ImageFilter.GaussianBlur(blur_radius))
                    return blurred_image
                else:
                    return image
            except Exception as e:
                print(f"Error processing image from {url}: {e}")
                return None
        else:
            print(f"Failed to fetch image from {url} - Status Code: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
            raise ValueError('图片获取失败')


async def fetch_images(image_urls, blur_radius=5,is_cache=False):
    try:
        tasks = [fetch_image_with_blur(url, blur_radius=blur_radius) for url in image_urls]
        images = await asyncio.gather(*tasks)
        return [img for img in images if img is not None]
    except Exception as e:
        print(f'触发报错:{repr(e)}')
        if not is_cache:
            return []
        else:
            raise e

def concatenate_images(text_image, images, margin=20):
    # 计算最终图片的宽度（以文本图片的宽度为基础）
    text_width, text_height = text_image.size
    total_height = text_height + margin * len(images)  # 间距
    max_image_height = 0
    
    # 调整所有截图的宽度与文本图片一致，并计算总高度
    resized_images = []
    for img in images:
        img_ratio = img.size[1] / img.size[0]  # 高宽比
        new_height = int(text_width * img_ratio)
        resized_img = img.resize((text_width, new_height))
        resized_images.append(resized_img)
        total_height += new_height
    
    # 创建一个新图像来拼接文本图片和截图
    final_image = Image.new('RGB', (text_width, total_height), color=(255, 255, 255))
    final_image.paste(text_image, (0, 0))
    
    # 拼接每个截图
    y_offset = text_height + margin
    for img in resized_images:
        final_image.paste(img, (0, y_offset))
        y_offset += img.size[1] + margin
    
    return final_image

async def generate_image_string(text, image_urls,blur_radius=10,is_cache=False):
    # 创建文本图片
    text_image = create_image_from_text(text)
    
    # 获取截图（异步获取）
    images = await fetch_images(image_urls,blur_radius,is_cache)
    
    # 拼接文本图片和截图
    final_image = concatenate_images(text_image, images)
    
    # 返回拼接后的图片的 base64 字符串
    return await image_to_base64(final_image)


async def analyze_torrent(torrent_url,gid):
    flag, magnet_url, torrent_hash = is_torrent(torrent_url)
    if not flag:
        msg = "这不是一个磁链或种子hash"
        return msg
    
    # 查看群设置
    image_set = False
    blur_radius = 10
    if group_config := await check_group_config(gid):
        image_set = group_config.get('image_set',False)
        blur_radius = group_config.get('blur_radius',10)

    # 先检查缓存
    cache_res = await check_cache(torrent_hash)
    if cache_res: # 命中缓存
        res = cache_res
        msg = f"种子哈希: {torrent_hash}\n"
        msg += f"文件类型：{res['type']}-{res['file_type']}\n"
        msg += f"种子名称: {util.filt_message(res['name'])}\n"
        msg += f"总大小: {hum_convert(res['size'])}\n"
        msg += f"文件总数：{res['count']}"
        # 获取截图
        screenshot_urls = []
        if image_set and (screenshots_data := res.get('screenshots',[])):
            if len(screenshots_data) > 0:
                msg += "\n种子截图："
                for i in res['screenshots'][:3]:  # 仅取前3个截图
                    screenshot_urls.append(i['screenshot'])
            try:
                return await generate_image_string(msg.strip(),screenshot_urls,blur_radius,is_cache=True)
            except:
                traceback.print_exc()
                print('缓存图片有问题 使用请求')
        else:
            # if len(res['screenshots']) > 0:
                # msg += "种子截图：\n"
                # for i in res['screenshots'][:3]:
                    # msg += f"  {i['screenshot']}\n"
            return msg.strip()
    # 未命中缓存
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
            ares = await aiorequests.get(url, timeout=10, headers=headers)
            res = await ares.json()
            if res['error'] == '':  # 失败时候error是quota_limited
                # 缓存结果
                await write_cache(torrent_hash, res)
                ok = True
                break
            await asyncio.sleep(3)
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
        screenshot_urls = []
        if image_set and (screenshots_data := res.get('screenshots',[])):
            if len(screenshots_data) > 0:
                msg += "\n种子截图："
                for i in res['screenshots'][:3]:  # 仅取前3个截图
                    screenshot_urls.append(i['screenshot'])
            return await generate_image_string(msg.strip(),screenshot_urls)
        else:
            # if len(res['screenshots']) > 0:
                # msg += "种子截图：\n"
                # for i in res['screenshots'][:3]:
                    # msg += f"  {i['screenshot']}\n"
            return msg.strip()


# debug
if __name__ == '__main__':
    if debug:
        loop = asyncio.new_event_loop()
        url = "ec809a3d681c2dda1bc1ae8feb84c4b8077896b2"
        print(loop.run_until_complete(analyze_torrent(url)))