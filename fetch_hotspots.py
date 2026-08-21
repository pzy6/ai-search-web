#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星图 HotMap - 热点数据抓取脚本
================================
抓取微博热搜、知乎热榜、B站热门、百度热搜，
生成结构化JSON供前端动态加载。

运行方式：
  python fetch_hotspots.py          # 抓取并保存到 hotspots.json
  python fetch_hotspots.py --dry-run  # 测试抓取，不保存文件
  python fetch_hotspots.py --debug  # 打印详细调试信息

GitHub Actions 会自动运行此脚本并提交更新。
"""

import json
import re
import time
import random
import hashlib
from datetime import datetime
from urllib.parse import quote
import argparse

try:
    import requests
except ImportError:
    print("错误：需要安装 requests 库")
    print("  pip install requests")
    raise SystemExit(1)

# ============================================================
# 配置
# ============================================================
OUTPUT_FILE = "hotspots.json"
MAX_RETRIES = 3
TIMEOUT = 15
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 分类映射：将抓取到的热点词映射到星图 HotMap 的10个分类
def guess_category(name):
    """根据热点名称猜测所属分类"""
    name_lower = name.lower()
    
    # 优先级高->低检查关键词
    category_keywords = {
        'tech': ['ai', '人工智能', 'chatgpt', 'deepseek', '芯片', '华为', '苹果', '小米', 'oppo', 'vivo', '三星', '索尼', '科技', '手机', '电脑', '笔记本', '互联网', '5g', '6g', 'vr', 'ar', '元宇宙', '机器人', '无人机', '自动驾驶', '新能源', '电动车', '特斯拉', '比亚迪', '蔚来', '小鹏', '理想', '太空', '火箭', '卫星', 'spacex', '星舰', '编程', '代码', '算法', '模型', 'gpt', 'llm', '大模型', '开源', '系统', 'windows', 'macos', 'ios', 'android', '鸿蒙', '像素', '像素风', '像素游戏', '影之刃', '黑神话', '游戏', '实机', '演示', '发布会', '芯片', '光刻', '半导体', '算力', '英伟达', 'nvidia', 'amd', 'intel'],
        'science': ['量子', '物理', '化学', '生物', '医学', '基因', '黑洞', '宇宙', '火星', '月球', '科学', '诺贝尔奖', '研究', '论文', '实验', '天文', 'nasa', 'spacex', '火星', '航天', '登月', '粒子', '对撞', 'dna', 'rna', '蛋白质', '细胞', '病毒', '疫苗', '药物', '临床', '试验'],
        'humanities': ['历史', '哲学', '文学', '社会学', '心理学', '考古', '文化', '传统', '诗词', '考古', '人文', '读书', '书籍', '古籍', '文物', '博物馆', '非遗', '民俗', '方言', '汉字', '语言', '翻译', '名著', '作家', '诗人', '小说', '散文'],
        'arts': ['电影', '音乐', '绘画', '艺术', '美术', '设计', '建筑', '雕塑', '摄影', '舞蹈', '戏剧', '演唱会', '画展', '潮流', '专辑', '单曲', '歌手', '乐队', '演奏', '编曲', '作词', '导演', '演员', '影后', '影帝', '票房', '奥斯卡', '戛纳', '柏林', '威尼斯', '电影节', '艺术展', '时装', '穿搭', 'ootd', '潮流', '时尚'],
        'lifestyle': ['美食', '旅行', '旅游', '穿搭', '家居', '健身', '减肥', 'citywalk', '露营', '骑行', '跑步', '瑜伽', 'city', 'walk', 'citywalk', '旅游', '美食', '穿搭', 'ootd', '家居', '装修', '民宿', '酒店', '探店', '打卡', '网红', '景点', '攻略', '出行', '周末', '假期', '假期', '度假', '露营', '徒步', '登山', '潜水', '滑雪', '冲浪', '钓鱼', 'city', 'walk', '自驾', '旅拍'],
        'health': ['健康', '养生', '减肥', '健身', '心理', '睡眠', '饮食', '营养', '疫苗', '医院', '医疗', '疾病', '中医', '瑜伽', '体检', '医保', '血压', '血糖', '血脂', '失眠', '焦虑', '抑郁', '心理健康', '冥想', '普拉提', '马拉松', '健身房', '私教', '蛋白粉', '维生素', '保健品'],
        'business': ['经济', '股票', '基金', '投资', '房地产', '房价', '创业', '就业', '工资', '人民币', '美元', '银行', '金融', '股市', 'a股', '港股', '美股', '基金', '期货', '债券', '理财', '保险', '汇率', '央行', '降息', '加息', '通胀', 'cpi', 'gdp', '财政', '税收', '贸易', '关税', '出口', '进口', '并购', 'ipo', '上市', '财报', '业绩', '营收', '利润'],
        'engineering': ['工程', '建筑', '桥梁', '高铁', '航空', '制造', '工业', '机械', '土木', '水利', '电力', '电网', '光伏', '风电', '核电', '水电', '隧道', '地铁', '港口', '机场', '大坝', '盾构', 'bim', 'cad', '3d打印', '智能制造', '工业机器人', '数控机床', '新材料', '碳纤维', '石墨烯'],
        'education': ['教育', '高考', '考研', '留学', '学校', '大学', '考试', '录取', '分数线', '志愿填报', '学生', '教师', '教材', '网课', '培训', '补习', '学区房', '双减', '减负', '素质教育', '职业教育', '本科', '硕士', '博士', '论文', '答辩', '毕业', '就业', '校招', '秋招', '春招', 'offer', '简历'],
        'environment': ['环境', '气候', '碳中和', '环保', '污染', '生态', '绿色', '可持续', '垃圾分类', '太阳能', '风能', '水资源', 'pm2.5', '雾霾', '温室', '全球变暖', '极端天气', '暴雨', '洪水', '干旱', '山火', '地震', '台风', '海啸', '核污水', '海洋', '森林', '湿地', '生物多样性', '物种灭绝', '保护', '地球日']
    }
    
    hot_keywords = ['热梗', '热搜', '爆', '新', '火', '热', '热门', '梗', '流行', '潮', '网红', ' viral', ' trending']
    
    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    
    # 默认分类：如果包含"热""爆"等词归为lifestyle热点
    for kw in hot_keywords:
        if kw in name_lower:
            return 'lifestyle'
    
    return 'tech'  # 默认科技类


# ============================================================
# 抓取函数
# ============================================================

def fetch_with_retry(url, headers=None, timeout=TIMEOUT, retries=MAX_RETRIES):
    """带重试的HTTP请求"""
    if headers is None:
        headers = {}
    headers.setdefault('User-Agent', random.choice(USER_AGENTS))
    headers.setdefault('Accept', 'application/json, text/plain, */*')
    headers.setdefault('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            print(f"  警告: {url} 返回状态码 {resp.status_code} (尝试 {attempt+1}/{retries})")
        except requests.exceptions.Timeout:
            print(f"  超时 (尝试 {attempt+1}/{retries}): {url}")
        except requests.exceptions.ConnectionError as e:
            print(f"  连接错误 (尝试 {attempt+1}/{retries}): {url} - {e}")
        except Exception as e:
            print(f"  请求异常 (尝试 {attempt+1}/{retries}): {url} - {e}")
        
        if attempt < retries - 1:
            time.sleep(1 + attempt)
    
    return None


def fetch_weibo_hot():
    """抓取微博热搜"""
    print("[1/4] 抓取微博热搜...")
    results = []
    
    # 尝试多个微博热搜接口
    endpoints = [
        "https://weibo.com/ajax/side/hotSearch",
    ]
    
    for url in endpoints:
        resp = fetch_with_retry(url)
        if resp is None:
            continue
            
        try:
            data = resp.json()
            # 微博热搜API返回格式
            if isinstance(data, dict) and 'data' in data:
                cards = data['data'].get('realtime', [])
                for item in cards[:30]:
                    name = item.get('word', '') or item.get('note', '')
                    if name:
                        hot = item.get('num', 0) or item.get('raw_hot', 0)
                        results.append({
                            'name': name.strip(),
                            'hot': int(hot) if hot else 0,
                            'source': 'weibo',
                            'url': f"https://s.weibo.com/weibo?q={quote(name)}"
                        })
                if results:
                    print(f"  ✓ 微博热搜: 抓取到 {len(results)} 条")
                    break
        except Exception as e:
            print(f"  解析失败: {e}")
            continue
    
    # 备用：如果API失败，尝试直接解析微博热搜页面
    if not results:
        try:
            resp = fetch_with_retry("https://s.weibo.com/top/summary?cate=realtimehot")
            if resp:
                html = resp.text
                # 解析热搜列表
                pattern = r'<td class="td-02">.*?<a href="/weibo\?q=([^"]+)"[^>]*>(.*?)</a>'
                matches = re.findall(pattern, html, re.DOTALL)
                for i, (q, name) in enumerate(matches[:30]):
                    clean_name = re.sub(r'<[^>]+>', '', name).strip()
                    if clean_name and clean_name not in [r['name'] for r in results]:
                        results.append({
                            'name': clean_name,
                            'hot': 1000000 - i * 30000,
                            'source': 'weibo',
                            'url': f"https://s.weibo.com/weibo?q={q}"
                        })
                if results:
                    print(f"  ✓ 微博热搜(备用): 抓取到 {len(results)} 条")
        except Exception as e:
            print(f"  备用抓取失败: {e}")
    
    return results


def fetch_zhihu_hot():
    """抓取知乎热榜"""
    print("[2/4] 抓取知乎热榜...")
    results = []
    
    try:
        # 知乎热榜API（不需要认证，但可能有频率限制）
        resp = fetch_with_retry(
            "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
            headers={'Referer': 'https://www.zhihu.com/'}
        )
        if resp:
            data = resp.json()
            if isinstance(data, dict) and 'data' in data:
                for item in data['data'][:30]:
                    target = item.get('target', {})
                    title = target.get('title', '') or item.get('title', '')
                    if title:
                        hot = item.get('detail_text', '0')
                        hot_num = int(re.search(r'(\d+)', hot).group(1)) if re.search(r'(\d+)', hot) else 0
                        qid = target.get('id', '')
                        results.append({
                            'name': title.strip(),
                            'hot': hot_num * 10000,
                            'source': 'zhihu',
                            'url': f"https://www.zhihu.com/question/{qid}" if qid else '#'
                        })
            if results:
                print(f"  ✓ 知乎热榜: 抓取到 {len(results)} 条")
    except Exception as e:
        print(f"  抓取失败: {e}")
    
    return results


def fetch_bilibili_hot():
    """抓取B站热门"""
    print("[3/4] 抓取B站热门...")
    results = []
    
    try:
        # B站热门视频API
        resp = fetch_with_retry(
            "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
            headers={'Referer': 'https://www.bilibili.com/'}
        )
        if resp:
            data = resp.json()
            if isinstance(data, dict) and data.get('code') == 0:
                for item in data['data']['list'][:20]:
                    title = item.get('title', '')
                    if title:
                        results.append({
                            'name': title.strip(),
                            'hot': item.get('stat', {}).get('view', 0),
                            'source': 'bilibili',
                            'url': f"https://www.bilibili.com/video/{item.get('bvid', '')}"
                        })
            if results:
                print(f"  ✓ B站热门: 抓取到 {len(results)} 条")
    except Exception as e:
        print(f"  抓取失败: {e}")
    
    return results


def fetch_baidu_hot():
    """抓取百度热搜"""
    print("[4/4] 抓取百度热搜...")
    results = []
    
    try:
        # 百度热搜API
        resp = fetch_with_retry("https://top.baidu.com/board?tab=realtime")
        if resp:
            html = resp.text
            # 提取百度热搜数据（JSON嵌入在页面中）
            json_match = re.search(r'<script id="sanRoot"[^>]*>(.*?)</script>', html, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    data = json.loads(json_str)
                    cards = data.get('data', {}).get('cards', [])
                    for card in cards:
                        content = card.get('content', [])
                        for item in content[:20]:
                            word = item.get('word', '')
                            if word:
                                results.append({
                                    'name': word.strip(),
                                    'hot': item.get('hotScore', 0),
                                    'source': 'baidu',
                                    'url': item.get('url', '#')
                                })
                except Exception as e:
                    print(f"  JSON解析失败: {e}")
            
            # 备用：正则提取
            if not results:
                pattern = r'"word":"([^"]+)".*?"hotScore":(\d+)'
                matches = re.findall(pattern, html)
                for word, hot in matches[:30]:
                    if word and word not in [r['name'] for r in results]:
                        results.append({
                            'name': word.strip(),
                            'hot': int(hot),
                            'source': 'baidu',
                            'url': '#'
                        })
            
            if results:
                print(f"  ✓ 百度热搜: 抓取到 {len(results)} 条")
    except Exception as e:
        print(f"  抓取失败: {e}")
    
    return results


# ============================================================
# 数据整合
# ============================================================

def merge_and_deduplicate(all_results, max_items=100):
    """合并结果并去重，按热度排序"""
    seen = set()
    merged = []
    
    # 按热度排序
    all_results.sort(key=lambda x: x.get('hot', 0), reverse=True)
    
    for item in all_results:
        name = item['name']
        # 简单去重：忽略空格和标点后的相似度
        key = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', name).lower()
        if key and key not in seen:
            seen.add(key)
            item['category'] = guess_category(name)
            item['id'] = hashlib.md5(name.encode()).hexdigest()[:8]
            merged.append(item)
    
    return merged[:max_items]


def generate_nodes(hotspots):
    """生成星图 HotMap 节点格式"""
    nodes = []
    categories = {
        'tech': '科技', 'science': '科学', 'humanities': '人文',
        'arts': '艺术', 'lifestyle': '生活', 'health': '健康',
        'business': '财经', 'engineering': '工程', 'education': '教育',
        'environment': '环境'
    }
    
    for i, h in enumerate(hotspots):
        cat = h['category']
        nodes.append({
            'id': f"hot_{h['id']}",
            'name': h['name'],
            'cat': cat,
            'hot': h['hot'],
            'source': h['source'],
            'url': h['url'],
            'category_name': categories.get(cat, '其他'),
            'is_hot': True
        })
    
    return nodes


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='星图 HotMap 热点数据抓取脚本')
    parser.add_argument('--dry-run', action='store_true', help='测试模式，不保存文件')
    parser.add_argument('--debug', action='store_true', help='打印调试信息')
    args = parser.parse_args()
    
    print("=" * 50)
    print("星图 HotMap - 热点数据抓取")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    all_results = []
    
    # 抓取各平台数据
    all_results.extend(fetch_weibo_hot())
    all_results.extend(fetch_zhihu_hot())
    all_results.extend(fetch_bilibili_hot())
    all_results.extend(fetch_baidu_hot())
    
    print(f"\n原始数据: {len(all_results)} 条")
    
    # 合并去重
    hotspots = merge_and_deduplicate(all_results, max_items=100)
    print(f"去重后: {len(hotspots)} 条")
    
    # 分类统计
    cat_stats = {}
    for h in hotspots:
        cat = h['category']
        cat_stats[cat] = cat_stats.get(cat, 0) + 1
    print("分类分布:", dict(sorted(cat_stats.items(), key=lambda x: -x[1])))
    
    # 生成节点
    nodes = generate_nodes(hotspots)
    
    # 输出数据
    output = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total': len(nodes),
            'sources': list(set(h['source'] for h in hotspots)),
            'version': '1.0'
        },
        'nodes': nodes
    }
    
    if args.debug:
        print("\n--- 前10条数据预览 ---")
        for n in nodes[:10]:
            print(f"  [{n['cat']}] {n['name']} (热度:{n['hot']}, 来源:{n['source']})")
    
    if args.dry_run:
        print("\n[DRY-RUN] 测试完成，不保存文件")
        print(f"将生成 {len(nodes)} 个节点")
    else:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 已保存到 {OUTPUT_FILE} ({len(nodes)} 个节点)")
    
    print("=" * 50)
    return 0 if nodes else 1


if __name__ == '__main__':
    exit(main())
