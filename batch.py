import os

from main import xet
import json

COURSE_IDs = [
    'term_62d507c0a9420_Ng2t4Q',
    'p_60852c5be4b09890f0e6d517',
    'course_2Lr3HOA8jCPiGoK0CkQ61WHbLvi',
    'course_2VHgnIutj2reVkVT1pMzDEvaGC6'
]


def gather_videos():
    videos = []
    for courcse_id in COURSE_IDs:
        resources = xet.list(courcse_id)
        for resource in resources:
            if 'section_id' in resource:
                if resource['title'] in {'完整跟练'} or '补丁包' in resource['title']:
                    videos += [dict(section=resource['title'], **x) for x in resource['videos']]
            elif '完整跟练' in resource['title']:
                videos.append(dict(section=None, **resource))
    return videos


if __name__ == '__main__':
    # videos = gather_videos()
    # with open('video.json', 'w') as f:
    #     json.dump(videos, f, indent=2, ensure_ascii=False)
    with open('video.json', 'r') as f:
        videos = json.load(f)
    rids = [x['resource_id'] for x in videos]
    xet.download(rids, False)
    # rids2 = []
    # for video in videos:
    #     path = os.path.join('download', video['resource_id'])
    #     files = os.listdir(path)
    #     if not any(f.endswith('.ts') for f in files):
    #         rids2.append(video)
    # print(rids2)
    # xet.download([x['resource_id'] for x in rids2], True, download_only=True)
    # for rid in rids:
    #     xet.transcode(rid)

    # url = 'W$siZGVmaW5pdGlvbl9uYW@lIjoiXHU5YWQ%XHU#ZTA@IiwiZGVmaW5pdGlvbl9wIjoiNzIwUCIsInVybCI6Imh0dHBzOlwvXC9idHQtdm9kLnhpYW9la#5vdy5jb#@cLzk$NjRhN#E@dm9kdHJhbnNnenAxMjUyNTI0MTI#XC85M#JjYmUxOTUyODU%OTA%MTc5ODQxMzkyNTZcL#RybVwvdi5mNDIxMjIwLm0zdTg/c#lnbj0zMzEyNjY5MzlhNDZhMDM@M#ZiOTM%NjE@YzgxZmE#YSZ0PTY@MGIxNDEzJnVzPVd6dFRqUHlOelEiLCJpc@9zdXBwb$J0IjpmYWxzZSwiZXh0Ijp7Imhvc$QiOiJodHRwczpcL@wvYnR0LXZvZC5%aWFvZWtub$cuY#9tIiwicGF0aCI6Ijk$NjRhN#E@dm9kdHJhbnNnenAxMjUyNTI0MTI#XC85M#JjYmUxOTUyODU%OTA%MTc5ODQxMzkyNTZcL#RybSIsInBhcmFtIjoic#lnbj0zMzEyNjY5MzlhNDZhMDM@M#ZiOTM%NjE@YzgxZmE#YSZ0PTY@MGIxNDEzJnVzPVd6dFRqUHlOelEifX@d'
    # res = xet.decrypt_url(url)
    # print(123)
