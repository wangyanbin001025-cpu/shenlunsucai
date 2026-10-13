#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RSS/Atom 更新器。默认仅存来源信息与学习整理结果；全文需有保存授权后手工导入。"""
from pathlib import Path
from datetime import datetime, date, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
from html.parser import HTMLParser
import json, re, sqlite3, hashlib
from db_layer import connect as connect_db

TOPIC_KEYS = {
    'law_enforcement':'行政执法', 'rural_revitalization':'乡村振兴', 'business_environment':'营商环境',
    'sci_tech_innovation':'科技创新', 'green_development':'绿色发展', 'industrial_upgrading':'产业升级',
    'digital_economy':'数字经济', 'cultural_confidence':'文化自信'
}

class TextExtractor(HTMLParser):
    BLOCK = {'p','div','br','li','h1','h2','h3','h4','article','section','tr'}
    SKIP = {'script','style','noscript','svg','nav','footer','header','form'}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP: self.skip += 1
        if not self.skip and tag in self.BLOCK: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip: self.skip -= 1
        if not self.skip and tag in self.BLOCK: self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)
    def text(self):
        s=''.join(self.parts).replace('\xa0',' ')
        return re.sub(r'\n\s*\n\s*\n+', '\n\n', re.sub(r'[ \t]+',' ',s)).strip()


def fetch(url, timeout=15):
    req=Request(url, headers={'User-Agent':'ShenlunMaterialLibrary/1.0 (personal study tool)','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml, text/html,*/*'})
    with urlopen(req, timeout=timeout) as r:
        raw=r.read(2_500_000)
        charset=r.headers.get_content_charset() or 'utf-8'
    try: return raw.decode(charset,errors='replace')
    except LookupError: return raw.decode('utf-8',errors='replace')


def local_name(tag): return tag.rsplit('}',1)[-1].lower()


def child_text(el, names):
    for ch in list(el):
        if local_name(ch.tag) in names:
            return ''.join(ch.itertext()).strip()
    return ''


def parse_feed(xml, source_name):
    root=ET.fromstring(xml); entries=[]
    for el in root.iter():
        if local_name(el.tag) not in {'item','entry'}: continue
        title=child_text(el, {'title'})
        link=''
        for ch in list(el):
            if local_name(ch.tag)=='link':
                link=ch.attrib.get('href','').strip() or (ch.text or '').strip()
                if ch.attrib.get('rel','alternate')=='alternate': break
        published=child_text(el, {'pubdate','published','updated','date','issued','created'})
        description=child_text(el, {'description','summary','subtitle','content','encoded'})
        if title and link: entries.append({'title':title, 'link':link, 'published':published, 'description':description, 'source_name':source_name})
    return entries


def parse_date(raw):
    raw=(raw or '').strip()
    if not raw: return None
    try:
        dt=parsedate_to_datetime(raw)
        if dt.tzinfo: dt=dt.astimezone()
        return dt.date().isoformat()
    except Exception: pass
    m=re.search(r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})',raw)
    if m:
        try: return date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except Exception: return None
    return None


def classify(text):
    t=text.lower()
    rules={
      'law_enforcement':['基层治理','行政执法','政务服务','民生','干部作风','法治政府','营商服务','执法'],
      'rural_revitalization':['乡村','农业','农村','粮食安全','农民','县域'],
      'business_environment':['营商环境','民营经济','消费','统一大市场','开放','外贸','企业'],
      'sci_tech_innovation':['科技创新','人才','科研','教育强国','基础研究','创新生态'],
      'green_development':['生态','绿色','低碳','双碳','环境保护','污染治理'],
      'industrial_upgrading':['制造业','产业升级','高质量发展','新质生产力','产业链','工业'],
      'digital_economy':['人工智能','数字化','数字经济','数据要素','智能经济','数字中国'],
      'cultural_confidence':['文化','非遗','文博','文旅','文明','爱国主义','中华优秀传统']}
    found=[]
    for key, words in rules.items():
        if any(w.lower() in t for w in words): found.append(key)
    return found[:3] or ['law_enforcement']


def ai_organize(cfg, article, article_text):
    ai=cfg.get('ai',{}); key=ai.get('api_key','').strip(); model=ai.get('model','').strip()
    if not key or not model: return None
    base=ai.get('base_url','https://api.openai.com/v1').rstrip('/')
    payload={
      'model':model, 'temperature':0.2, 'response_format':{'type':'json_object'},
      'messages':[
        {'role':'system','content':'你是公务员考试申论备考编辑。只输出合法JSON，不虚构文中不存在的政策、人物、数字和事实。文章全文受版权保护，不要复现大段原文；quotes只摘取极短词句，每条尽量不超过12个汉字，其他内容全部概括改写。未知内容填写空字符串或空数组。topics只允许使用以下英文key：'+','.join(TOPIC_KEYS.keys())+'.'},
        {'role':'user','content':json.dumps({
          'task':'按申论素材库字段整理文章，核心观点需准确，写作角度至少3个，quotes尽量5条短语；不要输出全文原文。',
          'required_json_fields':{'core_view':'string','quotes':['string'],'argument_structure':'string','topics':['English topic key'],'writing_angles':['string'],'original_summary':'string'},
          'article_metadata':{'title':article['title'],'column_author':article['source_name'],'publish_date':article['publish_date'],'source_url':article['link']},
          'article_text_for_analysis':article_text[:18000]
        },ensure_ascii=False)}
      ]
    }
    data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    req=Request(base+'/chat/completions',data=data,headers={'Content-Type':'application/json','Authorization':'Bearer '+key,'User-Agent':'ShenlunMaterialLibrary/1.0'},method='POST')
    with urlopen(req,timeout=60) as r: out=json.loads(r.read().decode('utf-8'))
    content=out['choices'][0]['message']['content']
    obj=json.loads(content)
    obj['topics']=[k for k in obj.get('topics',[]) if k in TOPIC_KEYS]
    if not obj['topics']: obj['topics']=classify(article['title']+' '+article_text[:1000])
    obj['quotes']=[str(x).strip() for x in obj.get('quotes',[]) if str(x).strip()][:5]
    obj['writing_angles']=[str(x).strip() for x in obj.get('writing_angles',[]) if str(x).strip()][:6]
    return obj


def run_update(db_path, config_path):
    config=json.loads(Path(config_path).read_text(encoding='utf-8'))
    sources=[s for s in config.get('sources',[]) if s.get('enabled') and s.get('feed_url','').strip()]
    if not sources:
        msg='未运行：请在 config.json 中启用至少一个来源并填写可访问的 RSS/Atom 地址。'
        c=connect_db(db_path); c.execute('INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_update',datetime.now().isoformat(timespec='seconds'))); c.execute('INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_update_message',msg)); c.commit(); c.close()
        return {'ok':False,'message':msg,'added':0,'drafts':0,'errors':[]}
    added=0; drafts=0; errors=[]; seen=0
    conn=connect_db(db_path)
    try:
        for source in sources:
            name=source.get('name','官方来源'); feed_url=source.get('feed_url','').strip()
            try:
                xml=fetch(feed_url); entries=parse_feed(xml,name)
                # Keep the update bounded and recent; true publication dates are mandatory.
                entries=entries[:20]
                for a in entries:
                    pub=parse_date(a.get('published'))
                    if not pub:
                        errors.append({'source':name,'title':a['title'],'reason':'RSS/Atom 条目没有可识别的真实发布日期，已跳过'}); continue
                    if pub>date.today().isoformat():
                        errors.append({'source':name,'title':a['title'],'reason':'发布日期晚于当前日期，已跳过'}); continue
                    if pub < '2025-01-01':
                        continue
                    url=urljoin(feed_url,a['link'])
                    dupe=conn.execute('SELECT id FROM materials WHERE source_url=? AND source_url<>\'\'',(url,)).fetchone()
                    if dupe: continue
                    seen+=1
                    text=''
                    try:
                        page=fetch(url); parser=TextExtractor(); parser.feed(page); text=parser.text()
                        if len(text)<120: text=(a.get('description','') or '').strip()
                    except Exception:
                        text=(a.get('description','') or '').strip()
                    organized=None
                    try: organized=ai_organize(config, {**a,'publish_date':pub}, text)
                    except Exception as e:
                        errors.append({'source':name,'title':a['title'],'reason':'AI 整理未完成：'+str(e)[:180]})
                    try: item_id=hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]
                    except Exception: item_id=hashlib.sha256((a['title']+pub).encode('utf-8')).hexdigest()[:24]
                    if organized:
                        core=organized.get('core_view','').strip(); summary=organized.get('original_summary','').strip()
                        status='published' if config.get('auto_publish') and core and summary and len(organized.get('writing_angles',[]))>=3 else 'draft'
                        if status=='draft': drafts+=1
                    else:
                        core=''; summary=(a.get('description','') or '').strip()
                        organized={'quotes':[],'argument_structure':'','topics':classify(a['title']+' '+summary),'writing_angles':[]}
                        status='draft'; drafts+=1
                    cur = conn.execute('''INSERT INTO materials(id,title,column_author,publish_date,source_name,source_url,core_view,quotes_json,argument_structure,topics_json,writing_angles_json,original_summary,original_content,status,created_at,updated_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING''',(
                        item_id,a['title'],name,pub,name,url,core,json.dumps(organized.get('quotes',[]),ensure_ascii=False),
                        organized.get('argument_structure',''),json.dumps(organized.get('topics',[]),ensure_ascii=False),
                        json.dumps(organized.get('writing_angles',[]),ensure_ascii=False),summary,'',status,
                        datetime.now().isoformat(timespec='seconds'),datetime.now().isoformat(timespec='seconds')))
                    if cur.rowcount == 1: added += 1
            except Exception as e: errors.append({'source':name,'reason':str(e)[:240]})
        msg=f'更新检查完成：新增 {added} 条（其中待审核 {drafts} 条），跳过重复或无真实日期条目。'
        if errors: msg+=f' 另有 {len(errors)} 项需要检查。'
        conn.execute('INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_update',datetime.now().isoformat(timespec='seconds')))
        conn.execute('INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_update_message',msg)); conn.commit()
        return {'ok':True,'message':msg,'added':added,'drafts':drafts,'errors':errors[:30],'checked_entries':seen}
    finally: conn.close()
