import asyncio
import base64
import json
import math
import os
from multiprocessing import Process, Queue
from urllib.parse import urlparse, quote, parse_qs

import aiohttp
import click
import ffmpy
import m3u8
import requests
from Crypto.Cipher import AES
from m3u8.model import SegmentList, Segment


class Xet(object):
    XIAO_E_TONG_BASE64_DICT = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0@#$%56789+/"
    STD_DICT = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/='
    DOWNLOAD_DIR = 'download'
    VIDEO_DIR = 'video'

    def __init__(self):
        self.configs = self.config('r') or {}
        self.session = self.login()

    def config(self, mode):
        try:
            if mode == 'r':
                with open("config.json", "r") as config_file:
                    obj = json.load(config_file)
                if 'cookie' in obj:
                    obj['cookies'] = dict(map(lambda x: x.strip().split('='), obj['cookie'].split(';')))
                return obj
            elif mode == 'w':
                with open("config.json", "w") as config_file:
                    json.dump(self.configs, config_file)
                    return True
        except:
            return

    def login(self):
        session = requests.Session()
        for key, value in self.configs['cookies'].items():
            session.cookies[key] = value
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        })
        return session

    @staticmethod
    def transform_type(id):
        transform_box = {'a': 'audio', 'v': 'video', 'p': 'product'}
        type = transform_box.get(id[0], None)
        if type:
            return type
        else:
            print('Invalid id. None suitable type')
            exit(1)

    def get_resource(self, resourceid):
        resourcetype = Xet.transform_type(resourceid)
        url = 'https://{appid}.h5.xiaoeknow.com/xe.course.business.{resourcetype}.detail_info.get/2.0.0'.format(
            appid=self.configs['appid'],
            resourcetype=resourcetype
        )
        body = {
            'bizData[resource_id]': resourceid,
            # bizData[product_id]: term_62d507c0a9420_Ng2t4Q
            'bizData[opr_sys]': 'MacIntel'
        }
        self.session.headers.update({
            'Referer': 'https://{appid}.h5.xiaoeknow.com/p/course/{resourcetype}/{resourceid}'.format(
                appid=self.configs['appid'], resourcetype=resourcetype, resourceid=resourceid)
        })
        res = self.session.post(url, data=body)
        if res.status_code == 200:
            content = res.json()
            if not content['code']:
                return content['data']
            else:
                print('status: {} msg: {}'.format(content['code'], content['msg']))
        return {}

    def decrypt_url(self, encrypted_url):
        encrypted_url = encrypted_url.replace('__ba', '')
        trans = encrypted_url.maketrans(Xet.XIAO_E_TONG_BASE64_DICT, Xet.STD_DICT)
        decrypted = base64.b64decode(encrypted_url.translate(trans)).decode()
        if not decrypted.endswith(']'):
            decrypted += '"}]'
        obj = json.loads(decrypted)
        return obj[0]

    def parse_m3u8(self, url_info, resource_id):
        url = url_info['url']
        self.session.headers.update(
            {'Referer': 'https://pc-shop.xiaoe-tech.com/{appid}/video_details?id={resourceid}'.format(
                appid=self.configs['appid'], resourceid=resource_id)})
        media_text = self.session.get(url).text
        media = m3u8.loads(media_text)
        key = None
        url_prefix = os.path.join(os.path.split(url.split('?')[0])[0], "{ts_file}")
        if 'private_index' in url:
            key_url = Xet.parse_key_url(media_text)
            key = Xet.get_key_from_url(key_url, self.configs['user_id'])
            url_prefix = os.path.join(url_info['ext']['host'], url_info['ext']['path'],
                                      f"{{ts_file}}&{url_info['ext']['param']}")
        print('Total: {} part'.format(len(media.data['segments'])))

        segment_props = []
        segments = SegmentList()
        for index, segment in enumerate(media.data['segments']):
            segment_props.append(dict(index=index, uri=segment.get('uri')))
            segment['uri'] = 'v_{}.ts'.format(index)
            segments.append(Segment(base_uri=None, **segment))
        return dict(url=url, url_prefix=url_prefix, media=media, key=key), segment_props, segments

    @staticmethod
    def parse_key_url(media_text):
        payload = media_text.split('#EXT-X-KEY:', maxsplit=1)[-1].split('\n')[0]
        pairs = dict(map(lambda x: x.strip().split('=', maxsplit=1), payload.split(',')))
        return pairs.get('URI', '').strip('"')

    @staticmethod
    def get_key_from_url(url, userid) -> str:
        # url拼接uid参数
        url += f'&uid={userid}'
        # 发送get请求
        rsp = requests.get(url=url)
        rsp_data = rsp.content
        if len(rsp_data) == 16:
            userid_bytes = bytes(userid.encode(encoding='utf-8'))
            result_list = []
            for index in range(0, len(rsp_data)):
                result_list.append(
                    rsp_data[index] ^ userid_bytes[index])
            # return base64.b64encode(bytes(result_list)).decode()
            return bytes(result_list)
        else:
            print(f"获取异常，请求返回值：{rsp.text}")
            return ''

    @staticmethod
    def before_download(index, nocache, resource_dir, title):
        ts_file = os.path.join(resource_dir, 'v_{}.ts'.format(index))
        if not nocache and os.path.exists(ts_file):
            print('Already Downloaded: {title} {file}'.format(title=title, file=ts_file))
            return None
        return ts_file

    @staticmethod
    def post_download(content, ts_file, key, title):
        if key is not None:
            cryptor = AES.new(key, AES.MODE_CBC)
            content = cryptor.decrypt(content)
        with open(ts_file + '.tmp', 'wb') as ts:
            ts.write(content)
        os.rename(ts_file + '.tmp', ts_file)
        print('Download Successful: {title} {file}'.format(title=title, file=ts_file))

    @staticmethod
    def download_video_segment(index, url, key, nocache, resource_dir, title):
        ts_file = Xet.before_download(index, nocache, resource_dir, title)
        if ts_file is None:
            return -1
        try:
            res = requests.get(url)
            assert res.status_code == 200
            content = res.content
            Xet.post_download(content, ts_file, key, title)
        except Exception as e:
            print(
                'Download Failed: {title} {file}\nError: {error}'.format(title=title, file=ts_file, error=repr(e)))
            return 0
        return 1

    @staticmethod
    async def download_video_segment_async(session, index, url, key, nocache, resource_dir, title):
        ts_file = Xet.before_download(index, nocache, resource_dir, title)
        if ts_file is None:
            return -1
        try:
            async with session.get(url) as res:
                assert res.status == 200
                content = await res.content.read()
            Xet.post_download(content, ts_file, key, title)
        except Exception as e:
            print(
                'Download Failed: {title} {file}\nError: {error}'.format(title=title, file=ts_file, error=repr(e)))
            return 0
        return 1

    async def _download_video_segment_core(self, segments, url_prefix, **kwargs):
        tasks = []
        async with aiohttp.ClientSession(headers=dict(self.session.headers)) as session:
            for item in segments:
                # kwargs=key, nocache, resource_dir, title
                params = dict(session=session, index=item['index'], url=url_prefix.format(ts_file=item['uri']),
                              **kwargs)
                tasks.append(asyncio.create_task(Xet.download_video_segment_async(**params)))
            return await asyncio.gather(*tasks)

    def download_video_core_async(self, segments, url_prefix, **kwargs):
        retry = 0
        total = len(segments)

        last_failed = None
        retry_count = 20
        if 'retry_count' in kwargs:
            retry_count = kwargs.pop('retry_count')
        n_downloaded, n_failed = 0, 0
        while retry < retry_count:
            results = asyncio.run(self._download_video_segment_core(segments, url_prefix, **kwargs))
            n_downloaded = sum(1 if x == 1 else 0 for x in results)
            n_failed = sum(1 if x == 0 else 0 for x in results)
            print(f"{total - n_failed}/{total} completed, {n_failed}/{total} failed")
            if n_failed == 0:
                break
            if last_failed is not None and n_failed > 0 and last_failed == n_failed:
                retry += 1
            last_failed = n_failed
        return n_downloaded > 0, n_failed == 0

    @staticmethod
    def download_video_core(segments, url_prefix, **kwargs):
        changed, complete = False, True
        for item in segments:
            res = Xet.download_video_segment(item['index'], url_prefix.format(ts_file=item['uri']), **kwargs)
            if res == 1:
                changed = True
            elif res == 0:
                complete = False
        return changed, complete

    def download_video(self, download_dir, resource, nocache=False, parallel=True):
        resource_dir = os.path.join(download_dir, resource['video_info']['resource_id'])
        os.makedirs(resource_dir, exist_ok=True)

        url_info = self.decrypt_url(resource['video_urls'])
        if 'ext' not in url_info or 'sign' not in url_info['url']:
            param = resource['video_info']['video_audio_url'].split('?', maxsplit=1)[-1]
            url = url_info['url']
            if 'sign' not in url:
                url_info['url'] = url + "?" + param
            if 'ext' not in url_info:
                host = '{uri.scheme}://{uri.netloc}'.format(uri=urlparse(url))
                path = "/".join(url.replace(host, '').split('/')[1:3])
                url_info['ext'] = dict(host=host, path=path, param=param)
        playlist, segment_props, segments = self.parse_m3u8(url_info, resource['video_info']['resource_id'])

        kwargs = dict(url_prefix=playlist['url_prefix'], key=playlist['key'], nocache=nocache,
                      resource_dir=resource_dir, title=resource['video_info']['file_name'])
        if parallel:
            changed, complete = self.download_video_core_async(segment_props, **kwargs)
        else:
            changed, complete = Xet.download_video_core(segment_props, **kwargs)

        media = playlist['media']
        m3u8_file = os.path.join(resource_dir, 'video.m3u8')
        if changed or not os.path.exists(m3u8_file):
            media.segments = segments
            with open(m3u8_file, 'w', encoding='utf8') as f:
                f.write(media.dumps())
        metadata = {'title': resource['video_info']['file_name'], 'complete': complete}
        with open(os.path.join(download_dir, resource['video_info']['resource_id'], 'metadata'), 'w') as f:
            json.dump(metadata, f)
        return

    @staticmethod
    def transcode(resourceid, output_dir=None):
        output_dir = output_dir or Xet.VIDEO_DIR
        os.makedirs(output_dir, exist_ok=True)
        resource_dir = os.path.join(Xet.DOWNLOAD_DIR, resourceid)
        if os.path.exists(resource_dir) and os.path.exists(os.path.join(resource_dir, 'metadata')):
            with open(os.path.join(resource_dir, 'metadata')) as f:
                metadata = json.load(f)
            if metadata['complete']:
                output_file = os.path.join(output_dir, metadata['title'])
                if os.path.exists(output_file):
                    os.remove(output_file)
                ff = ffmpy.FFmpeg(inputs={os.path.join(resource_dir, 'video.m3u8'): ['-protocol_whitelist',
                                                                                     'crypto,file,http,https,tcp,tls']},
                                  outputs={output_file: None})
                print(ff.cmd)
                ff.run()
        return

    @staticmethod
    def transcode_worker(queue, output_dir=None):
        while True:
            rid = queue.get()
            print(rid)
            if rid is None:
                break
            Xet.transcode(rid, output_dir)

    def download(self, resource_ids, nocahce=False, parallel_download=True, transcode_workers=4, output_dir=None,
                 download_only=False):
        os.makedirs(Xet.DOWNLOAD_DIR, exist_ok=True)
        resource_list = [self.get_resource(id) for id in resource_ids]

        qq = None
        processes = []
        if transcode_workers > 1:
            qq = Queue()
            for i in range(transcode_workers):
                worker = Process(target=Xet.transcode_worker, args=(qq, output_dir))
                worker.daemon = True
                worker.start()  # Launch reader_p() as another proc
                processes.append(worker)

        for resource in resource_list:
            try:
                self.download_video(Xet.DOWNLOAD_DIR, resource, nocahce, parallel_download)
                if not download_only:
                    if qq is not None:
                        qq.put(resource['video_info']['resource_id'])
                    else:
                        self.transcode(resource['video_info']['resource_id'])
            except Exception as e:
                import traceback

                traceback.print_exc()

        if qq is not None:
            for worker in processes:
                qq.put(None)
            for worker in processes:
                worker.join()

    def _list_sections(self, course_id, is_course):
        appid = self.configs['appid']
        sections = []
        url = f'https://{appid}.h5.xiaoeknow.com/xe.course.business.camp.catalog.get/2.0.0'
        refer = f'https://{appid}.h5.xiaoeknow.com/p/course/camp/{course_id}'
        payload = {
            'bizData[term_id]': course_id,
        }
        page_idx = 1
        page_size = 50
        if is_course:
            url = f'https://{appid}.h5.xiaoeknow.com/xe.course.business.avoidlogin.e_course.resource_catalog_list.get/1.0.0'
            refer = f'https://{appid}.h5.xiaoeknow.com/p/course/ecourse/{course_id}'
            payload = {
                'bizData[app_id]': appid,
                # 'bizData[resource_id]: i_65017184e4b064a863b7c2b2,
                'bizData[course_id]': course_id,
                'bizData[p_id]': 0,
                'bizData[order]': 'asc',
                'bizData[page]': page_idx,
                'bizData[page_size]': page_size
            }
        self.session.headers.update({'Referer': refer})
        while True:
            response = self.session.post(url, params=payload)
            response.raise_for_status()
            res = response.json()
            if res['code'] == 0:
                resources = res['data']['list'] if is_course else res['data']
                for section in resources:
                    id_key = 'chapter_id' if is_course else 'id'
                    title_key = 'chapter_title' if is_course else 'title'
                    sections.append(dict(section_id=section[id_key], title=section[title_key], videos=[]))
                pages = math.ceil(res['data']['total'] / page_size) if is_course else 1
                if pages == page_idx:
                    break
                page_idx += 1
                payload.update({'bizData[page]': page_idx})
        return sections

    def _list_with_sections(self, course_id, is_course):
        appid = self.configs['appid']
        sections = self._list_sections(course_id, is_course)
        for section in sections:
            url = f'https://{appid}.h5.xiaoeknow.com/xe.course.business.camp.node.get/2.0.0'
            refer = f'https://{appid}.h5.xiaoeknow.com/p/course/camp/{course_id}'
            payload = {
                'bizData[term_id]': course_id,
                'bizData[node_id]': section['section_id']
            }
            page_idx = 1
            page_size = 50
            if is_course:
                url = f'https://{appid}.h5.xiaoeknow.com/xe.course.business.avoidlogin.e_course.resource_catalog_list.get/1.0.0'
                refer = f'https://{appid}.h5.xiaoeknow.com/p/course/ecourse/{course_id}'
                payload = {
                    'bizData[app_id]': appid,
                    # 'bizData[resource_id]: i_65017184e4b064a863b7c2b2,
                    'bizData[course_id]': course_id,
                    'bizData[p_id]': section['section_id'],
                    'bizData[order]': 'asc',
                    'bizData[page]': page_idx,
                    'bizData[page_size]': page_size
                }
            self.session.headers.update({'Referer': refer})
            while True:
                response = self.session.post(url, params=payload)
                response.raise_for_status()
                res = response.json()
                if res['code'] == 0:
                    resources = res['data']['list'] if is_course else res['data']
                    for resource in resources:
                        id_key = 'chapter_id' if is_course else 'id'
                        title_key = 'chapter_title' if is_course else 'title'
                        if resource[id_key].startswith('v_'):
                            section['videos'].append(dict(resource_id=resource[id_key], title=resource[title_key]))
                    pages = math.ceil(res['data']['total'] / page_size) if is_course else 1
                    if pages == page_idx:
                        break
                    page_idx += 1
                    payload.update({'bizData[page]': page_idx})
        return sections

    def _list_product(self, course_id):
        appid = self.configs['appid']
        url = f'https://{appid}.h5.xiaoeknow.com/xe.course.business.column.items.get/2.0.0'
        page_idx = 1
        page_size = 20
        payload = {
            'bizData[column_id]': course_id,
            'bizData[page_index]': page_idx,
            'bizData[page_size]': page_size,
            'bizData[sort]': 'desc'
        }
        refer = f'https://{appid}.h5.xiaoeknow.com/p/course/column/{course_id}?type=3'
        self.session.headers.update({'Referer': refer})
        videos = []
        while True:
            response = self.session.post(url, params=payload)
            response.raise_for_status()
            res = response.json()
            if res['code'] == 0:
                for resource in res['data']['list']:
                    if resource['resource_id'].startswith('v_'):
                        videos.append(dict(resource_id=resource['resource_id'], title=resource['resource_title']))
                pages = math.ceil(res['data']['total'] / page_size)
                if pages == page_idx:
                    break
                page_idx += 1
                payload.update({'bizData[page_index]': page_idx})
        return videos

    def _list_course(self, course_id):
        sections = self._list_sections(course_id, True)

    def list(self, course_id):
        if course_id.startswith('p_'):
            return self._list_product(course_id)
        return self._list_with_sections(course_id, course_id.startswith('course_'))


xet = Xet()


@click.group(context_settings=dict(help_option_names=['-h', '--help'], ignore_unknown_options=True))
def main():
    pass


@main.command()
@click.option('--transcode-workers', '-tw', required=False, default=4, type=click.INT,
              help='Whether to transcode in parallel')
@click.option('--parallel-download', '-pd', required=False, default=True, type=click.BOOL,
              help='Whether to download the segments in parallel')
@click.option('--cache', '-c', required=False, default=True, type=click.BOOL,
              help='Whether to skip downloaded segments')
@click.option('--output-dir', '-o', required=False, default=None, type=click.STRING,
              help="The directory path to save the video")
@click.option('--download-only', '-d', required=False, default=False, type=click.BOOL,
              help='Whether to skip downloaded segments')
@click.argument('resource_ids', required=True, type=click.STRING, nargs=-1)
def download(resource_ids, transcode_workers, parallel_download, cache, output_dir, download_only):
    """Download videos"""
    xet.download(resource_ids, not cache, parallel_download, transcode_workers, output_dir)


@main.command()
@click.option('--output', '-o', required=False, default=None, type=click.STRING,
              help="The file path to save the video list")
@click.argument('course_id', required=True, type=click.STRING)
def list(course_id, output):
    """List all the video info in a course"""
    sections = xet.list(course_id)
    if output is not None:
        with open(output, 'w') as fobj:
            json.dump(sections, fobj, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(sections, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
