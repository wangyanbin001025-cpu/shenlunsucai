const state = {
  topics: [], items: [], user: null, stats: {total: 0, favorites: 0, drafts: 0},
  page: 'home', selectedTopic: '', archiveQuery: '', authMode: 'login', expandedOriginal: false,
  update: null, detailId: null, toastTimer: null, isOffline: false
};
const pageLabels = {home:'总览首页', topics:'主题分类', archive:'历史归档', favorites:'我的收藏', offline:'离线阅读', updates:'每日更新'};
const OFFLINE_SNAPSHOT_KEY = 'shenlun-offline-snapshot-v2';
const OFFLINE_PINNED_KEY = 'shenlun-offline-pinned-v2';
function readPinnedOffline() { try { const x=JSON.parse(localStorage.getItem(OFFLINE_PINNED_KEY)||'[]'); return Array.isArray(x)?x:[]; } catch { return []; } }
function storePinnedOffline(items) { localStorage.setItem(OFFLINE_PINNED_KEY, JSON.stringify(items)); }
function favoriteQueueKey(username) { return `shenlun-favorite-queue-v1:${username||'guest'}`; }
function readFavoriteQueue(username) { try { const x=JSON.parse(localStorage.getItem(favoriteQueueKey(username))||'[]'); return Array.isArray(x)?x:[]; } catch { return []; } }
function storeFavoriteQueue(username, items) { localStorage.setItem(favoriteQueueKey(username), JSON.stringify(items)); }
const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];

async function api(url, options={}) {
  const opt = {...options, headers: {...(options.headers||{})}};
  if (opt.body && typeof opt.body !== 'string') { opt.headers['Content-Type']='application/json'; opt.body=JSON.stringify(opt.body); }
  const res = await fetch(url, opt);
  let data={}; try { data=await res.json(); } catch {}
  if (!res.ok) { const err=new Error(data.error || `请求失败（${res.status}）`); err.status=res.status; throw err; }
  return data;
}
function esc(value='') { return String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function safeText(value='') { return esc(value).replace(/\n/g,'<br>'); }
function showToast(message) {
  const el=$('#toast'); el.textContent=message; el.classList.add('show');
  clearTimeout(state.toastTimer); state.toastTimer=setTimeout(()=>el.classList.remove('show'),3000);
}
function topicLabel(key) { return state.topics.find(t=>t.key===key)?.label || key; }
function topicObject(key) { return state.topics.find(t=>t.key===key) || {key,label:key,en:'',description:'',icon:'•'}; }
function setNetworkStatus(online, label) {
  const el=$('#network-status'); if(!el)return;
  el.textContent=label || (online?'在线同步':'离线阅读');
  el.classList.toggle('offline',!online);
  document.body.classList.toggle('offline-mode',!online);
}
function saveOfflineSnapshot(meta, items) {
  // Cache a useful recent window; explicit offline pins retain a longer copy separately.
  try {
    const compact=(items||[]).slice(0,120).map(x=>({...x, original_content:String(x.original_content||'').slice(0,8000)}));
    localStorage.setItem(OFFLINE_SNAPSHOT_KEY, JSON.stringify({saved_at:new Date().toISOString(),meta,items:compact}));
  } catch (e) {
    try {
      const compact=(items||[]).slice(0,35).map(x=>({...x, original_content:String(x.original_content||'').slice(0,1500)}));
      localStorage.setItem(OFFLINE_SNAPSHOT_KEY, JSON.stringify({saved_at:new Date().toISOString(),meta,items:compact}));
    } catch (e2) { console.warn('本地离线缓存空间不足',e2); }
  }
}
function readOfflineSnapshot() { try { const x=JSON.parse(localStorage.getItem(OFFLINE_SNAPSHOT_KEY)||'null'); return x&&Array.isArray(x.items)?x:null; } catch { return null; } }
function saveItemForOffline(id) {
  const item=getItem(id); if(!item){showToast('找不到这条素材');return;}
  let pins=readPinnedOffline();
  pins=pins.filter(x=>x.id!==item.id);
  pins.unshift({...item, original_content:String(item.original_content||'').slice(0,35000), offline_saved_at:new Date().toISOString()});
  // Keep the offline shelf bounded to protect the device's browser storage.
  pins=pins.slice(0,20);
  try { storePinnedOffline(pins); renderOfflinePage(); showToast('已保存到本设备的离线阅读'); }
  catch(e) { showToast('设备存储空间不足，请先清理离线素材'); }
  if(!$('#detail-modal').classList.contains('hidden') && state.detailId===id) $('#detail-content').innerHTML=detailHtml(getItem(id));
}
function removeOfflineItem(id) {
  storePinnedOffline(readPinnedOffline().filter(x=>x.id!==id));
  renderOfflinePage();
  if(!$('#detail-modal').classList.contains('hidden') && state.detailId===id) $('#detail-content').innerHTML=detailHtml(getItem(id));
  showToast('已从离线阅读中移除');
}
function isSavedOffline(id) { return readPinnedOffline().some(x=>x.id===id); }
function renderOfflinePage() {
  const pins=readPinnedOffline();
  $('#offline-count').textContent=`${pins.length} 篇已保存到本设备`;
  $('#offline-list').innerHTML=pins.length?pins.map(item=>`<article class="material-card offline-material-card"><div class="material-date"><b>${esc(dateParts(item.publish_date).day)}</b><span>${esc(dateParts(item.publish_date).month)}</span></div><div class="material-card-main"><button class="material-card-title" data-action="detail" data-id="${esc(item.id)}">${esc(item.title)}</button><div class="material-card-meta">${esc(item.column_author||item.source_name||'个人整理')} · ${formatDate(item.publish_date,true)}</div><div class="topic-tags">${topicTags(item)}</div><p class="material-excerpt">${esc(item.core_view||item.original_summary||'打开查看完整素材')}</p></div><div class="material-card-actions"><button class="outline-small" data-action="detail" data-id="${esc(item.id)}">打开阅读</button><button class="outline-small" data-action="remove-offline" data-id="${esc(item.id)}">移除</button></div></article>`).join(''):emptyState('还没有保存离线素材','先在线打开一篇素材，再点击详情中的“保存离线”。最多保留最近保存的 20 篇。','浏览主题素材','topics');
}
async function copyText(text) {
  try {
    if(navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else {
      const ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();
      const ok=document.execCommand('copy');ta.remove();if(!ok)throw new Error('复制失败');
    }
    showToast('已复制到剪贴板'); return true;
  } catch(e) { showToast('复制失败，请长按文字手动复制'); return false; }
}
async function syncFavoriteQueue() {
  if(!navigator.onLine || !state.user || state.isOffline) return false;
  const username=state.user.username; const queue=readFavoriteQueue(username); if(!queue.length)return false;
  const remaining=[]; let changed=false;
  for(const op of queue) {
    try { await api(`/api/favorites/${encodeURIComponent(op.id)}`,{method:op.saved?'POST':'DELETE'}); changed=true; }
    catch(e) { remaining.push(op); }
  }
  storeFavoriteQueue(username,remaining);
  if(changed) showToast('离线期间的收藏已同步');
  return changed;
}
function getItem(id) { const remote=state.items.find(x=>x.id===id); const pinned=readPinnedOffline().find(x=>x.id===id); return state.isOffline ? (pinned||remote) : (remote||pinned); }
function latestPublished() { return state.items.filter(x=>x.status!=='draft').sort((a,b)=>(b.publish_date||'').localeCompare(a.publish_date||'')); }
function countByTopic(key) { return latestPublished().filter(x=>(x.topics||[]).includes(key)).length; }
function formatDate(dateStr, includeYear=false) {
  if (!dateStr) return '日期未记录';
  const p=dateStr.split('-'); return includeYear ? `${p[0]}年${Number(p[1])}月${Number(p[2])}日` : `${p[1]}.${p[2]}`;
}
function dateParts(dateStr) { const p=(dateStr||'').split('-'); return {day:p[2]||'—',month:p[1]?`${p[1]}月`:'日期待核'}; }
function topicTags(item) { return (item.topics||[]).map(k=>`<span class="topic-tag">${esc(topicLabel(k))}</span>`).join(''); }
function emptyState(title, desc, actionLabel='', action='') {
  return `<div class="empty-state"><div class="empty-illustration">▤</div><h3>${esc(title)}</h3><p>${esc(desc)}</p>${actionLabel?`<button class="primary-button" data-action="${esc(action)}">${esc(actionLabel)}</button>`:''}</div>`;
}
function favoriteButton(item, className='mini-action') {
  const saved=!!item.is_favorite;
  return `<button class="${className}${saved?' saved':''}" data-action="favorite" data-id="${esc(item.id)}" data-fav="${saved?'1':'0'}" title="${saved?'取消收藏':'收藏素材'}">${saved?'♥':'♡'}</button>`;
}
function renderTopicCards(container, large=false) {
  const el=typeof container==='string'?$(container):container;
  el.innerHTML=state.topics.map(t=>`<button class="topic-card" data-action="choose-topic" data-topic="${esc(t.key)}">
    <div class="topic-card-top"><span class="topic-symbol">${esc(t.icon||'•')}</span><span class="topic-arrow">↗</span></div>
    <h3>${esc(t.label)}</h3><div class="topic-en">${esc(t.en||'')}</div><p>${esc(t.description||'')}</p>
    <div class="topic-card-bottom"><span>已整理素材</span><strong>${countByTopic(t.key)} 篇</strong></div></button>`).join('');
}
function renderStats() {
  $('#stat-total').innerHTML=`${state.stats.total||0}<span> 篇</span>`;
  $('#stat-topics').innerHTML=`${state.topics.length}<span> 类</span>`;
  $('#stat-favorites').innerHTML=`${state.user ? (state.stats.favorites||0) : '—'}<span> 篇</span>`;
  $('#stat-drafts').innerHTML=`${state.stats.drafts||0}<span> 篇</span>`;
  $('#nav-topic-count').textContent=state.topics.length;
  $('#user-label').textContent=state.user ? state.user.username : '登录 / 注册';
  $('#user-avatar').textContent=state.user ? (state.user.username.slice(0,1)||'学') : '学';
}
function renderLatest() {
  const items=latestPublished().slice(0,5);
  $('#latest-list').innerHTML=items.length?items.map(item=>{
    const d=dateParts(item.publish_date);
    return `<div class="latest-item"><div class="date-block"><b>${esc(d.day)}</b><span>${esc(d.month)}</span></div><div class="latest-main"><button class="latest-title" data-action="detail" data-id="${esc(item.id)}">${esc(item.title)}</button><div class="latest-meta">${esc(item.column_author||item.source_name||'未标注栏目')} · ${formatDate(item.publish_date,true)}</div><p class="latest-summary">${esc(item.core_view||item.original_summary||'这条素材尚未补充摘要，可打开详情继续整理。')}</p></div><div class="item-actions">${favoriteButton(item)}</div></div>`;
  }).join(''):emptyState('素材库还没有文章','你可以先手动新增一条素材，或配置来源后运行更新任务。','新增第一条素材','add');
}
function renderHome() { renderStats(); renderTopicCards('#home-topic-grid'); renderLatest(); }
function materialCard(item, archive=false) {
  const d=dateParts(item.publish_date);
  return `<article class="material-card"><div class="material-date"><b>${esc(d.day)}</b><span>${esc(d.month)}</span></div><div class="material-card-main"><button class="material-card-title" data-action="detail" data-id="${esc(item.id)}">${esc(item.title)}</button>${item.status==='draft'?'<span class="draft-tag">待整理</span>':''}<div class="material-card-meta">${esc(item.column_author||item.source_name||'未标注栏目')} · ${formatDate(item.publish_date,true)}</div><div class="topic-tags">${topicTags(item)}</div><p class="material-excerpt">${esc(item.core_view||item.original_summary||'暂无摘要，点击标题补充素材要点。')}</p></div><div class="material-card-actions">${favoriteButton(item,'mini-action')}<button class="outline-small" data-action="detail" data-id="${esc(item.id)}">查看详情</button></div></article>`;
}
function renderTopicPage() {
  renderTopicCards('#all-topic-grid',true);
  const key=state.selectedTopic; const name=key?topicLabel(key):'全部主题素材';
  $('#topic-list-heading').textContent=name;
  const q=($('#topic-search').value||'').trim().toLowerCase();
  let items=latestPublished().filter(x=>!key||(x.topics||[]).includes(key));
  if(q) items=items.filter(x=>`${x.title} ${x.core_view} ${x.original_summary} ${(x.quotes||[]).join(' ')}`.toLowerCase().includes(q));
  if($('#topic-sort').value==='asc') items.reverse();
  $('#topic-list-count').textContent=`共 ${items.length} 篇 · 按主题和关键词筛选`;
  $('#topic-material-list').innerHTML=items.length?items.map(x=>materialCard(x)).join(''):emptyState('这个主题还没有素材','可以新增文章并选择对应主题，也可以稍后导入已整理的 JSON 数据。','新增素材','add');
}
function populateArchiveTopic() {
  const el=$('#archive-topic'); if (el.options.length>1) return;
  state.topics.forEach(t=>{const o=document.createElement('option');o.value=t.key;o.textContent=t.label;el.append(o);});
}
function renderArchive() {
  populateArchiveTopic();
  const from=$('#archive-from').value, to=$('#archive-to').value, topic=$('#archive-topic').value;
  const q=state.archiveQuery.toLowerCase();
  let items=state.items.filter(x=>x.status!=='draft');
  if(from) items=items.filter(x=>x.publish_date>=from); if(to) items=items.filter(x=>x.publish_date<=to);
  if(topic) items=items.filter(x=>(x.topics||[]).includes(topic));
  if(q) items=items.filter(x=>`${x.title} ${x.core_view} ${x.original_summary} ${(x.quotes||[]).join(' ')} ${x.argument_structure}`.toLowerCase().includes(q));
  items.sort((a,b)=>(b.publish_date||'').localeCompare(a.publish_date||''));
  if(!items.length) { $('#archive-content').innerHTML=emptyState(q?`没有找到“${state.archiveQuery}”相关素材`:'暂无归档记录','添加素材或调整筛选条件后，这里会按年份和月份整理你的阅读记录。','新增素材','add');return; }
  const years={};
  items.forEach(it=>{const year=(it.publish_date||'日期待核').slice(0,4);const month=(it.publish_date||'').slice(5,7)||'未知月份';(years[year]??={})[month]??=[];years[year][month].push(it);});
  $('#archive-content').innerHTML=Object.keys(years).sort((a,b)=>b.localeCompare(a)).map(year=>`<section class="archive-group"><h2 class="archive-year">${esc(year)} <span style="font:10px sans-serif;color:#a0aaa0;letter-spacing:0">年 · ${Object.values(years[year]).flat().length} 篇</span></h2>${Object.keys(years[year]).sort((a,b)=>b.localeCompare(a)).map(month=>`<div class="archive-month">${esc(month==='未知月份'?'日期待核':Number(month)+' 月')} · ${years[year][month].length} 篇</div><div class="archive-items">${years[year][month].map(x=>materialCard(x,true)).join('')}</div>`).join('')}</section>`).join('');
}
async function renderFavorites() {
  if(!state.user) { $('#favorites-list').innerHTML=emptyState('登录后查看你的收藏','收藏重要观点、金句和写作角度，集中整理成个人复习清单。','登录 / 注册','auth'); $('#favorites-count').textContent='暂未登录'; return; }
  try {
    let items=[];
    if(state.isOffline) items=state.items.filter(x=>x.is_favorite);
    else { const data=await api('/api/materials?status=all&favorite=1&limit=1000'); items=data.items||[]; }
    const q=($('#favorites-search').value||'').trim().toLowerCase();
    if(q) items=items.filter(x=>`${x.title} ${x.core_view} ${x.original_summary} ${(x.quotes||[]).join(' ')}`.toLowerCase().includes(q));
    $('#favorites-count').textContent=`共 ${items.length} 篇${state.isOffline?'（本地缓存）':'收藏素材'}`;
    $('#favorites-list').innerHTML=items.length?items.map(x=>materialCard(x)).join(''):emptyState(state.isOffline?'本地缓存中没有收藏':'还没有收藏素材','在素材详情或列表中点击爱心，即可把内容收进复习清单。','浏览主题素材','topics');
  } catch(e) { $('#favorites-list').innerHTML=emptyState('暂时无法读取收藏',e.message,'登录 / 注册','auth'); }
}
function showPage(page) {
  if(!pageLabels[page] && page!=='home') return;
  state.page=page;
  $$('.page-view').forEach(el=>el.classList.toggle('hidden',el.id!==`page-${page}`));
  $$('.nav-item[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $$('.mobile-nav-item[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('#breadcrumb-current').textContent=pageLabels[page]||'总览首页';
  if(page==='home') renderHome();
  if(page==='topics') renderTopicPage();
  if(page==='archive') renderArchive();
  if(page==='favorites') renderFavorites();
  if(page==='offline') renderOfflinePage();
  if(page==='updates') loadUpdateStatus();
  window.scrollTo({top:0,behavior:'smooth'});
}
async function refreshData() {
  try {
    const [meta,items]=await Promise.all([api('/api/meta'),api('/api/materials?status=all&limit=1000')]);
    state.topics=meta.topics||[];state.user=meta.user||null;state.stats=meta.stats||{};state.items=items.items||[];state.isOffline=false;
    const remotePins=readPinnedOffline(); if(remotePins.length){const byId=new Map(state.items.map(x=>[x.id,x]));storePinnedOffline(remotePins.map(pin=>byId.has(pin.id)?{...pin,is_favorite:!!byId.get(pin.id).is_favorite}:pin));}
    saveOfflineSnapshot({topics:state.topics,user:state.user,stats:state.stats},state.items);
    setNetworkStatus(true);
  } catch(e) {
    const snapshot=readOfflineSnapshot();
    if(!snapshot) throw e;
    state.topics=snapshot.meta?.topics||state.topics;state.user=snapshot.meta?.user||state.user;state.stats=snapshot.meta?.stats||state.stats;state.items=snapshot.items||[];state.isOffline=true;
    setNetworkStatus(false,'离线阅读模式');
  }
  renderStats();
  if(state.page==='home') renderHome();
  else if(state.page==='topics') renderTopicPage();
  else if(state.page==='archive') renderArchive();
  else if(state.page==='favorites') await renderFavorites();
  else if(state.page==='offline') renderOfflinePage();
}
function openModal(id) { $('#'+id).classList.remove('hidden'); document.body.style.overflow='hidden'; }
function closeModal(id) { $('#'+id).classList.add('hidden'); if(!$$('.modal-backdrop:not(.hidden)').length) document.body.style.overflow=''; }
function openAuth() { $('#auth-error').textContent='';$('#auth-heading').textContent=state.authMode==='login'?'登录素材库':'创建账号';$('#auth-submit').textContent=state.authMode==='login'?'登录':'创建账号';$('#auth-password').value='';openModal('auth-modal'); }
function setAuthMode(mode) { state.authMode=mode;$('#auth-heading').textContent=mode==='login'?'登录素材库':'创建账号';$('#auth-submit').textContent=mode==='login'?'登录':'创建账号';$('#auth-switch').innerHTML=mode==='login'?'还没有账号？<b>创建账号</b>':'已有账号？<b>返回登录</b>';$('#auth-password').autocomplete=mode==='login'?'current-password':'new-password';$('#auth-error').textContent=''; }
function openEditor(item=null) {
  if(state.isOffline){showToast('离线模式下暂不能新增或修改，联网后即可保存');return;}
  if(!state.user){setAuthMode('login');openAuth();showToast('登录后即可管理个人素材');return;}
  if(item && !item.can_edit){showToast('这条素材为只读内容');return;}
  $('#material-form').reset(); $('#edit-id').value=item?.id||''; $('#editor-title').textContent=item?'编辑学习素材':'新增学习素材';
  const localNow=new Date();const localToday=`${localNow.getFullYear()}-${String(localNow.getMonth()+1).padStart(2,'0')}-${String(localNow.getDate()).padStart(2,'0')}`;
  $('#f-title').value=item?.title||'';$('#f-author').value=item?.column_author||'';$('#f-date').value=item?.publish_date||localToday;$('#f-source').value=item?.source_name||'';$('#f-url').value=item?.source_url||'';$('#f-core').value=item?.core_view||'';$('#f-quotes').value=(item?.quotes||[]).join('\n');$('#f-structure').value=item?.argument_structure||'';$('#f-angles').value=(item?.writing_angles||[]).join('\n');$('#f-summary').value=item?.original_summary||'';$('#f-content').value=item?.original_content||'';$('#f-draft').checked=item?.status==='draft';
  $('#editor-topic-checkboxes').innerHTML=state.topics.map(t=>`<label class="topic-choice"><input type="checkbox" name="f-topics" value="${esc(t.key)}" ${(item?.topics||[]).includes(t.key)?'checked':''}/> ${esc(t.label)}</label>`).join('');
  openModal('editor-modal');
}
function openDetail(id) {
  const item=getItem(id); if(!item) return;
  state.detailId=id; state.expandedOriginal=false;
  $('#detail-content').innerHTML=detailHtml(item);
  openModal('detail-modal');
}
function detailHtml(item) {
  const quotes=(item.quotes||[]).length?`<div class="quote-toolbar"><span>共 ${(item.quotes||[]).length} 条表达</span><button class="small-text-action" data-action="copy-all-quotes" data-id="${esc(item.id)}">复制全部金句 ⧉</button></div><div class="quote-list">${item.quotes.map((q,i)=>`<div class="quote-item"><span>“${esc(q)}”</span><button class="quote-copy" data-action="copy-quote" data-id="${esc(item.id)}" data-quote-index="${i}" aria-label="复制这条金句">复制</button></div>`).join('')}</div>`:`<p>尚未整理金句，可点击“编辑素材”补充短句或关键词。</p>`;
  const angles=(item.writing_angles||[]).length?`<ol class="angle-list">${item.writing_angles.map((a,i)=>`<li><span>${String(i+1).padStart(2,'0')}</span><div>${esc(a)}</div></li>`).join('')}</ol>`:`<p>暂未添加写作角度，建议至少整理三个与不同题型相关的切入点。</p>`;
  const content=item.original_content||'';const preview=content.length>300?content.slice(0,300)+'…':content;
  const management=item.can_edit&&!state.isOffline?`<button class="outline-small" data-action="edit" data-id="${esc(item.id)}">✎ 编辑素材</button><button class="outline-small" data-action="delete" data-id="${esc(item.id)}">删除</button>`:'';
  const offlineButton=`<button class="outline-small" data-action="save-offline" data-id="${esc(item.id)}">${isSavedOffline(item.id)?'✓ 已保存离线':'⇩ 保存离线'}</button>`;
  return `<div class="detail-kicker">申论素材卡 <span>·</span> ${esc(item.source_name||'个人整理')}</div><h1 class="detail-title">${esc(item.title)}</h1><div class="detail-actions">${favoriteButton(item,'outline-small')}${offlineButton}${management}</div><div class="detail-meta"><span>▦ ${esc(item.column_author||'栏目 / 作者未标注')}</span><span>◷ ${formatDate(item.publish_date,true)}</span><span>来源：${esc(item.source_name||'未标注')}</span>${item.status==='draft'?'<span class="draft-tag">待整理</span>':''}</div>
  <div class="detail-section"><h3>01 核心观点概括</h3><div class="detail-callout">${esc(item.core_view||'尚未概括核心观点。建议用一句话说明“文章主张什么、为什么、怎么办”。')}</div></div>
  <div class="detail-section"><h3>02 好词好句 / 金句摘录</h3>${quotes}</div>
  <div class="detail-section"><h3>03 论证结构 / 框架</h3><div class="structure-box">${safeText(item.argument_structure||'尚未整理论证框架。可以尝试从提出问题、分析原因、提出对策三个层次梳理。')}</div></div>
  <div class="detail-section"><h3>04 申论主题标签</h3><div class="topic-tags">${topicTags(item)||'<span class="muted">尚未选择主题</span>'}</div></div>
  <div class="detail-section"><h3>05 可用于申论的写作角度</h3>${angles}</div>
  <div class="detail-section"><h3>06 原文摘要（正文要点）</h3><p>${safeText(item.original_summary||'暂未填写原文摘要。')}</p></div>
  <div class="detail-section"><h3>07 原文来源</h3><p>${esc(item.source_name||'未标注来源')}${item.source_url?`<br>${esc(item.source_url)}`:''}</p><div class="detail-source">来源地址以纯文本保存，不提供外部跳转。</div></div>
  <div class="detail-section"><h3>08 原文全文</h3><div class="original-box">${content?`<div class="original-text ${content.length>300&&!state.expandedOriginal?'original-preview':''}" id="original-fulltext">${esc(content.length>300&&!state.expandedOriginal?preview:content)}</div>${content.length>300?`<div class="original-controls"><small>${state.isOffline?'当前显示的是本地缓存内容':'全文来自你录入或获授权保存的内容'}</small><button class="small-text-action" data-action="toggle-original">${state.expandedOriginal?'收起全文':'展开阅读全文'} <span>${state.expandedOriginal?'↑':'↓'}</span></button></div>`:''}`:`<div class="original-text">暂无原文全文。可在“编辑素材”中粘贴自有或已获授权的正文；自动更新默认仅整理观点与摘要。</div>`}</div></div>
  <div class="detail-section"><h3>09 学习提示</h3><p>尝试将这条素材转换成“观点句 + 原因分析 + 对策建议”的三句表达，并结合具体题目判断是否适用。</p></div>`;
}
async function toggleFavorite(id, currentlySaved) {
  if(!state.user){setAuthMode('login');openAuth();showToast('登录后即可收藏重点素材');return;}
  const item=getItem(id);
  if(state.isOffline || !navigator.onLine) {
    if(!item){showToast('素材尚未缓存，联网后请重新打开');return;}
    item.is_favorite=!currentlySaved;
    state.items=state.items.map(x=>x.id===id?{...x,is_favorite:!currentlySaved}:x);
    const pins=readPinnedOffline();if(pins.some(x=>x.id===id))storePinnedOffline(pins.map(x=>x.id===id?{...x,is_favorite:!currentlySaved}:x));
    state.stats.favorites=Math.max(0,(state.stats.favorites||0)+(currentlySaved?-1:1));
    const username=state.user.username; const queue=readFavoriteQueue(username).filter(op=>op.id!==id);queue.push({id,saved:!currentlySaved});storeFavoriteQueue(username,queue);
    saveOfflineSnapshot({topics:state.topics,user:state.user,stats:state.stats},state.items);
    renderStats();if(state.page==='favorites')await renderFavorites();
    if(!$('#detail-modal').classList.contains('hidden') && state.detailId===id) $('#detail-content').innerHTML=detailHtml(item);
    showToast(!currentlySaved?'已暂存离线收藏，联网后同步':'已暂存取消收藏，联网后同步');return;
  }
  try {
    await api(`/api/favorites/${encodeURIComponent(id)}`,{method:currentlySaved?'DELETE':'POST'});
    await refreshData();
    if(!$('#detail-modal').classList.contains('hidden') && state.detailId===id) $('#detail-content').innerHTML=detailHtml(getItem(id));
    showToast(currentlySaved?'已取消收藏':'已加入我的收藏');
  } catch(e) {
    if(e.status===401) { setAuthMode('login');openAuth(); }
    else if(!e.status && item) { state.isOffline=true;item.is_favorite=!currentlySaved;state.items=state.items.map(x=>x.id===id?{...x,is_favorite:!currentlySaved}:x);const pins=readPinnedOffline();if(pins.some(x=>x.id===id))storePinnedOffline(pins.map(x=>x.id===id?{...x,is_favorite:!currentlySaved}:x));state.stats.favorites=Math.max(0,(state.stats.favorites||0)+(currentlySaved?-1:1));const username=state.user.username;const queue=readFavoriteQueue(username).filter(op=>op.id!==id);queue.push({id,saved:!currentlySaved});storeFavoriteQueue(username,queue);saveOfflineSnapshot({topics:state.topics,user:state.user,stats:state.stats},state.items);setNetworkStatus(false,'离线阅读模式');if(!$('#detail-modal').classList.contains('hidden')&&state.detailId===id)$('#detail-content').innerHTML=detailHtml(item);showToast('网络未连接，收藏将在恢复联网后同步'); }
    else showToast(e.message);
  }
}
async function submitMaterial(event) {
  event.preventDefault();
  const item={
    title:$('#f-title').value,column_author:$('#f-author').value,publish_date:$('#f-date').value,source_name:$('#f-source').value,source_url:$('#f-url').value,
    core_view:$('#f-core').value,quotes:$('#f-quotes').value.split('\n').map(s=>s.trim()).filter(Boolean),argument_structure:$('#f-structure').value,
    topics:$$('input[name="f-topics"]:checked').map(x=>x.value),writing_angles:$('#f-angles').value.split('\n').map(s=>s.trim()).filter(Boolean),original_summary:$('#f-summary').value,original_content:$('#f-content').value,status:$('#f-draft').checked?'draft':'published'
  };
  const id=$('#edit-id').value; if(id)item.id=id;
  $('#save-material-btn').disabled=true;$('#save-material-btn').textContent='保存中…';
  try { await api(id?`/api/materials/${encodeURIComponent(id)}`:'/api/materials',{method:id?'PUT':'POST',body:item}); closeModal('editor-modal');await refreshData();showToast(id?'素材已更新':'素材已保存'); if(state.page==='home') renderHome(); }
  catch(e){showToast(e.message);}
  finally{$('#save-material-btn').disabled=false;$('#save-material-btn').textContent='保存素材';}
}
async function loadUpdateStatus() {
  try {
    const d=await api('/api/update/status');state.update=d;
    const enabled=(d.sources||[]).filter(s=>s.enabled&&s.feed_url).length;
    $('#source-enabled-tag').textContent=`${enabled} 个已启用`;
    $('#source-list').innerHTML=(d.sources||[]).map((s,i)=>`<div class="source-item"><div class="source-monogram">${['人','求','党','讲'][i]||'源'}</div><div class="source-info"><b>${esc(s.name||'未命名来源')}</b><small>${esc(s.feed_url||'尚未配置 RSS / Atom 地址')}</small></div><span class="source-state ${s.enabled&&s.feed_url?'enabled':''}">${s.enabled&&s.feed_url?'已启用':'待配置'}</span></div>`).join('')||'<div class="muted">请在 config.json 中配置来源。</div>';
    $('#update-summary-title').textContent=enabled?`已配置 ${enabled} 个更新来源`:'更新任务尚未配置完成';
    $('#update-summary-desc').textContent=d.ai_configured?'AI 服务已配置，可以执行素材整理。':`AI 服务未配置：抓取到的条目将保存为“待整理”，不会虚构观点或金句。`;
    $('#update-last-run').textContent=d.last_update?`上次检查：${d.last_update} · ${d.last_update_message||''}`:'尚无运行记录';
    $('#update-log').innerHTML=`<span class="log-dot"></span> ${esc(d.last_update_message||'系统等待首次运行。')}`;
    $('#run-update-btn').disabled=!enabled;
    $('#run-update-btn').title=enabled?'':'请先配置至少一个来源地址并启用';
  } catch(e){$('#update-summary-title').textContent='读取更新任务状态失败';$('#update-summary-desc').textContent=e.message;}
}
async function runUpdate() {
  const btn=$('#run-update-btn'); if(btn.disabled)return;
  btn.disabled=true;btn.textContent='检查中…';$('#update-log').innerHTML='<span class="log-dot"></span> 正在读取 RSS 来源与检查重复条目，请稍候。';
  try { const res=await api('/api/update/run',{method:'POST',body:{}});showToast(res.message||'更新检查完成');$('#update-log').innerHTML=`<span class="log-dot"></span> ${esc(res.message||'更新检查完成')}`;await refreshData();await loadUpdateStatus(); }
  catch(e){showToast(e.message);$('#update-log').innerHTML=`<span class="log-dot"></span> ${esc(e.message)}`;await loadUpdateStatus();}
  finally{btn.disabled=false;btn.innerHTML='立即检查更新 <span>↗</span>';}
}
async function doGlobalSearch() {
  const q=$('#global-search-input').value.trim(); state.archiveQuery=q;
  if(!q){showToast('请输入要检索的关键词');return;}
  showPage('archive'); renderArchive();
}
async function exportData() {
  try { const d=await api('/api/export'); const blob=new Blob([JSON.stringify(d,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`申论素材库_${new Date().toISOString().slice(0,10)}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);showToast(`已导出 ${d.items.length} 条素材`); }
  catch(e){showToast(e.message);}
}
async function importData(file) {
  try { const d=JSON.parse(await file.text());const res=await api('/api/import',{method:'POST',body:d});await refreshData();showToast(`导入完成：新增 ${res.added}，更新 ${res.updated}，跳过 ${res.skipped.length}`);if(res.skipped.length) console.warn('导入时跳过的素材',res.skipped); }
  catch(e){showToast('导入失败：'+e.message);}
  finally{$('#import-file').value='';}
}

// Event delegation keeps controls functional after each render.
document.addEventListener('click', async (event)=>{
  const close=event.target.closest('[data-close]'); if(close){closeModal(close.dataset.close);return;}
  const pageBtn=event.target.closest('[data-page]'); if(pageBtn){showPage(pageBtn.dataset.page);return;}
  const actionBtn=event.target.closest('[data-action]'); if(!actionBtn)return;
  const action=actionBtn.dataset.action, id=actionBtn.dataset.id;
  if(action==='detail') openDetail(id);
  else if(action==='favorite') await toggleFavorite(id,actionBtn.dataset.fav==='1');
  else if(action==='choose-topic') {state.selectedTopic=actionBtn.dataset.topic; showPage('topics'); $('#topic-list-heading').textContent=topicLabel(state.selectedTopic); $('#topic-material-list').scrollIntoView({behavior:'smooth',block:'start'});}
  else if(action==='add') openEditor();
  else if(action==='auth') openAuth();
  else if(action==='edit') {const it=getItem(id); if(it){closeModal('detail-modal');openEditor(it);}}
  else if(action==='delete') {if(confirm('确定删除这条素材吗？该操作不可撤销。')){try{await api(`/api/materials/${encodeURIComponent(id)}`,{method:'DELETE'});closeModal('detail-modal');await refreshData();showToast('素材已删除');}catch(e){showToast(e.message);}}}
  else if(action==='toggle-original') {state.expandedOriginal=!state.expandedOriginal;const it=getItem(state.detailId);if(it)$('#detail-content').innerHTML=detailHtml(it);}
  else if(action==='save-offline') saveItemForOffline(id);
  else if(action==='remove-offline') removeOfflineItem(id);
  else if(action==='copy-quote') { const it=getItem(id); const q=it?.quotes?.[Number(actionBtn.dataset.quoteIndex)]; if(q) await copyText(q); }
  else if(action==='copy-all-quotes') { const it=getItem(id); if(it?.quotes?.length) await copyText(it.quotes.map((q,i)=>`${i+1}. ${q}`).join('\n')); else showToast('这篇素材还没有整理金句'); }
});
$$('.nav-item[data-page]').forEach(btn=>btn.addEventListener('click',()=>showPage(btn.dataset.page)));
$('#add-material-nav').addEventListener('click',()=>openEditor());
$('#mobile-add-btn').addEventListener('click',()=>openEditor());
$('#topic-add-btn').addEventListener('click',()=>openEditor());
$('#clear-offline-btn').addEventListener('click',()=>{if(confirm('确定清空本设备保存的离线素材吗？不会删除云端原始素材。')){storePinnedOffline([]);renderOfflinePage();showToast('离线素材已清空');}});
$('#material-form').addEventListener('submit',submitMaterial);
$('#topic-search').addEventListener('input',renderTopicPage);
$('#topic-sort').addEventListener('change',renderTopicPage);
$('#archive-filter-btn').addEventListener('click',renderArchive);
$('#archive-clear-btn').addEventListener('click',()=>{$('#archive-from').value='';$('#archive-to').value='';$('#archive-topic').value='';state.archiveQuery='';$('#global-search-input').value='';renderArchive();});
$('#favorites-search').addEventListener('input',renderFavorites);
$('#global-search-input').addEventListener('keydown',e=>{if(e.key==='Enter')doGlobalSearch();});
$('#export-btn').addEventListener('click',exportData);
$('#import-btn').addEventListener('click',()=>$('#import-file').click());
$('#import-file').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)importData(file);});
$('#user-chip').addEventListener('click',()=>{if(!state.user){setAuthMode('login');openAuth();}else if(confirm(`当前登录：${state.user.username}\n确定退出登录吗？`)){api('/api/auth/logout',{method:'POST',body:{}}).then(async()=>{state.user=null;await refreshData();showToast('已退出登录');}).catch(e=>showToast(e.message));}});
$('#auth-switch').addEventListener('click',()=>setAuthMode(state.authMode==='login'?'register':'login'));
$('#auth-form').addEventListener('submit',async e=>{
  e.preventDefault();$('#auth-error').textContent='';const username=$('#auth-username').value.trim(),password=$('#auth-password').value;
  try{const res=await api(`/api/auth/${state.authMode}`,{method:'POST',body:{username,password}});state.user=res.user;closeModal('auth-modal');await refreshData();showToast(state.authMode==='login'?'登录成功':'账号创建成功');if(state.page==='favorites')renderFavorites();}
  catch(err){$('#auth-error').textContent=err.message;}
});
$('#run-update-btn').addEventListener('click',runUpdate);
$('#download-report-btn').addEventListener('click',async()=>{try{const res=await fetch('/api/daily-report');if(!res.ok){let d={};try{d=await res.json()}catch{};throw new Error(d.error||'暂时无法下载今日文档');}const blob=await res.blob();const disposition=res.headers.get('Content-Disposition')||'';let filename='申论素材整理_'+new Date().toISOString().slice(0,10)+'.md';const match=disposition.match(/filename\*=UTF-8''([^;]+)/i);if(match)filename=decodeURIComponent(match[1]);const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=filename;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(u);showToast('今日整理文档已生成');}catch(e){showToast(e.message);}});
$$('[data-close]').forEach(btn=>btn.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal(btn.dataset.close);}));
$$('.modal-backdrop').forEach(backdrop=>backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeModal(backdrop.id);}));
document.addEventListener('keydown',e=>{if(e.key==='Escape') $$('.modal-backdrop:not(.hidden)').forEach(el=>closeModal(el.id)); if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#global-search-input').focus();}});

window.addEventListener('online',async()=>{
  setNetworkStatus(true,'正在同步…');
  try { await refreshData(); const changed=await syncFavoriteQueue(); if(changed) await refreshData(); showToast(state.isOffline?'网络已连接，但服务器暂不可用':'网络已恢复'); }
  catch(e) { setNetworkStatus(false,'离线阅读模式'); }
});
window.addEventListener('offline',()=>{state.isOffline=true;setNetworkStatus(false,'离线阅读模式');showToast('已切换到离线阅读模式');});
window.addEventListener('pageshow',async()=>{if(navigator.onLine){try{await refreshData();const changed=await syncFavoriteQueue();if(changed)await refreshData();}catch(e){setNetworkStatus(false,'离线阅读模式');}}});
if('serviceWorker' in navigator) window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(e=>console.warn('Service Worker 注册失败',e)));
(async function init(){
  const now=new Date();$('#today-date').innerHTML=`${String(now.getMonth()+1).padStart(2,'0')}<span>/</span>${String(now.getDate()).padStart(2,'0')}`;
  try {
    await refreshData();
    if(!state.isOffline) { const changed=await syncFavoriteQueue(); if(changed) await refreshData(); }
    showPage('home');
  } catch(e){setNetworkStatus(false,'尚无离线缓存');showToast('首次使用需要联网连接服务器');console.error(e);}
})();
