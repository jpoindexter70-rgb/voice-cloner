'use strict';
const $ = id => document.getElementById(id);
let token, profiles = [], assets = [], settings = {}, currentJob = null, resultAsset = null;
let recorder, stream, context, analyser, animation, timerHandle, startedAt, pauseStarted, pausedMs = 0, recordingProfile;
let recordedBlob, recordedUrl, chunks = [], recordingMime;
const titles = {dashboard:'Dashboard',myvoice:'My Voice',recorder:'Voice Recorder',generate:'Generate Speech',library:'Voice Library',editor:'Audio Editor',settings:'Settings',engine:'Engine Status'};
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
function notify(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; $('notice').hidden = false; }
async function api(path, options = {}) {
  const headers = {'X-VCR-Token':token, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  const response = await fetch('/api' + path, {...options, headers});
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body));
  return body;
}
function protect(action) { return async event => { try { await action(event); } catch (error) { notify(error.message, true); } }; }
function show(page) {
  if (!titles[page]) page = 'dashboard';
  document.querySelectorAll('.page').forEach(section => section.hidden = section.id !== page);
  document.querySelectorAll('nav button').forEach(button => button.classList.toggle('active',button.dataset.page === page));
  $('breadcrumb').textContent = titles[page]; location.hash = page;
  if (page === 'engine') diagnostics().catch(error => notify(error.message,true));
  if (page === 'editor') editorSelection().catch(error => notify(error.message,true));
}
document.querySelectorAll('[data-page],[data-go]').forEach(button => button.addEventListener('click', () => show(button.dataset.page || button.dataset.go)));
window.addEventListener('hashchange', () => show(location.hash.slice(1)));
async function confirmDelete(message) {
  $('confirm-message').textContent = message; $('confirm-dialog').showModal();
  return new Promise(resolve => {
    const finish = result => { $('confirm-dialog').close(); $('confirm-no').onclick = null; $('confirm-yes').onclick = null; $('confirm-dialog').onclose = null; resolve(result); };
    $('confirm-no').onclick = () => finish(false); $('confirm-yes').onclick = () => finish(true);
    $('confirm-dialog').onclose = () => finish(false);
  });
}
function options(select, items, label, fallback) {
  const previous = select.value;
  select.replaceChildren();
  items.forEach(item => { const option = document.createElement('option'); option.value = item.id; option.textContent = label(item); select.append(option); });
  if (items.some(item => item.id === previous)) select.value = previous;
  else if (fallback) select.value = fallback;
}
async function refresh() {
  [profiles, assets, settings] = await Promise.all([api('/profiles'),api('/assets'),api('/settings')]);
  $('profile-count').textContent = profiles.length;
  $('reference-count').textContent = assets.filter(a=>a.kind === 'reference').length;
  $('generated-count').textContent = assets.filter(a=>a.kind === 'generated').length;
  ['record-profile','generate-profile'].forEach(id=>options($(id), profiles, p=>p.name, 'my-voice'));
  options($('edit-asset'), assets, a=>`${profiles.find(p=>p.id===a.profile_id)?.name} · ${a.name}`);
  $('setting-engine').value = settings.engine; $('setting-device').value = settings.device;
  const turbo = settings.engine === 'turbo'; $('exaggeration').disabled = turbo; $('cfg').disabled = turbo;
  $('engine-controls-note').textContent = turbo ? 'Turbo does not support CFG or expression exaggeration; these controls are disabled. Turbo accepts tags such as [laugh] in your script.' : 'Original Chatterbox exposes CFG and expression. Changes may affect identity and pace.';
  renderAssets($('recent-assets'),assets.slice(0,5));
  renderAssets($('my-references'),assets.filter(a=>a.profile_id==='my-voice' && a.kind==='reference'));
  renderProfiles(); await engineSummary(); await renderReviews();
}
function renderAssets(container, list) {
  container.replaceChildren();
  if (!list.length) { container.innerHTML='<div class="empty">No recordings yet. Add a reference to get started.</div>'; return; }
  list.forEach(asset => {
    const profile = profiles.find(p=>p.id===asset.profile_id);
    const row = document.createElement('div'); row.className='asset-row';
    row.innerHTML = `<span class="asset-icon">≋</span><div class="asset-info"><strong>${escapeText(asset.name)}</strong><small>${escapeText(profile?.name)} · ${asset.metadata.seconds}s · ${asset.kind==='generated'?'AI-GENERATED':profile?.primary_asset===asset.id?'PRIMARY REFERENCE':'REFERENCE'}</small>${asset.metadata.warnings?.length?`<p class="footnote">${escapeText(asset.metadata.warnings.join(' '))}</p>`:''}</div><audio controls preload="none" src="/api/assets/${asset.id}/audio"></audio><div class="asset-actions"></div>`;
    const actions=row.querySelector('.asset-actions');
    const button = (label, action) => { const b=document.createElement('button'); b.className='secondary'; b.textContent=label; b.addEventListener('click',protect(action)); actions.append(b); };
    if (asset.kind==='reference' && profile?.primary_asset!==asset.id) button('Use reference', async()=>{ await api(`/profiles/${profile.id}/primary/${asset.id}`,{method:'POST'}); await refresh(); notify('Primary reference saved for this speaker.'); });
    button('Edit',()=>{ $('edit-asset').value=asset.id; show('editor'); });
    if (asset.kind==='generated') button('Compare',()=>showResult(asset));
    ['wav','mp3'].forEach(format=>{ const a=document.createElement('a'); a.className='button secondary'; a.href=`/api/assets/${asset.id}/export/${format}`; a.download=''; a.textContent=format.toUpperCase(); actions.append(a); });
    button('Delete',async()=>{ if(await confirmDelete('Delete this recording and its evaluations from active local storage? Exports and backups are separate.')) { await api(`/assets/${asset.id}`,{method:'DELETE'}); await refresh(); notify('Recording deleted.'); } });
    container.append(row);
  });
}
function renderProfiles() {
  $('profile-list').replaceChildren();
  profiles.forEach(profile=>{
    const card=document.createElement('article'); card.className='card';
    card.innerHTML=`<div class="card-title"><h2>${escapeText(profile.name)}</h2><span class="badge">${profile.id==='my-voice'?'DEFAULT':profile.kind.toUpperCase()}</span></div><p class="footnote">${escapeText(profile.authorization)} · Created ${escapeText(new Date(profile.created).toLocaleDateString())}</p><div class="actions"></div><div class="profile-assets"></div>`;
    const actions=card.querySelector('.actions');
    const addButton=(label,action,danger=false)=>{const b=document.createElement('button');b.textContent=label;b.className=danger?'danger':'secondary';b.addEventListener('click',protect(action));actions.append(b);};
    addButton('Test voice',()=>{$('generate-profile').value=profile.id;show('generate');});
    addButton('Record',()=>{$('record-profile').value=profile.id;show('recorder');});
    addButton('Rename',async()=>{const name=prompt('New profile name',profile.name);if(name?.trim()){await api(`/profiles/${profile.id}`,{method:'PATCH',body:{name:name.trim()}});await refresh();}});
    addButton(profile.id==='my-voice'?'Clear My Voice data':'Delete profile',async()=>{if(await confirmDelete(`Delete all active recordings, generated clips, and evaluations for ${profile.name}? ${profile.id==='my-voice'?'The empty default profile remains.':''} Exports and backups are separate.`)){await api(`/profiles/${profile.id}`,{method:'DELETE'});await refresh();notify('Profile data deleted.');}},true);
    const form=document.createElement('form');
    form.innerHTML='<label>Add reference recording<input type="file" accept="audio/*" required></label><label class="checkbox"><input type="checkbox" required> I have authorization to store this speaker’s audio.</label><button class="secondary">Upload reference</button>';
    form.addEventListener('submit',protect(async event=>{event.preventDefault();const file=form.querySelector('[type=file]').files[0];const check=form.querySelector('[type=checkbox]').checked;await uploadReference(profile.id,file,check);await refresh();}));
    card.append(form);renderAssets(card.querySelector('.profile-assets'),assets.filter(a=>a.profile_id===profile.id));$('profile-list').append(card);
  });
}
async function uploadReference(profileId,file,consent) {
  if(!file) throw new Error('Choose a recording first.');
  const data=new FormData();data.append('file',file);data.append('consent',String(consent));
  const asset=await api(`/profiles/${profileId}/references`,{method:'POST',body:data});notify('Reference saved locally. '+asset.metadata.warnings.join(' '));return asset;
}
$('my-upload').addEventListener('submit',protect(async event=>{event.preventDefault();await uploadReference('my-voice',$('my-file').files[0],$('my-consent').checked);await refresh();$('my-file').value='';}));
$('profile-kind').addEventListener('change',()=>{const child=$('profile-kind').value==='child';$('guardian-label').hidden=!child;$('profile-guardian').required=child;});
$('profile-form').addEventListener('submit',protect(async event=>{event.preventDefault();await api('/profiles',{method:'POST',body:{name:$('profile-name').value,kind:$('profile-kind').value,guardian:$('profile-guardian').value,consent:$('profile-consent').checked}});event.target.reset();$('guardian-label').hidden=true;$('profile-guardian').required=false;await refresh();notify('Independent voice profile created. Add this speaker’s references.');}));
$('settings-form').addEventListener('submit',protect(async event=>{event.preventDefault();await api('/settings',{method:'PUT',body:{engine:$('setting-engine').value,device:$('setting-device').value}});await refresh();notify('Settings saved. The previous model was unloaded.');}));
['temperature','exaggeration','cfg'].forEach(id=>$(id).addEventListener('input',()=>$(id+'-value').textContent=$(id).value));
$('test-my-voice').addEventListener('click',()=>{$('generate-profile').value='my-voice';});
$('script').addEventListener('input',()=>$('char-count').textContent=`${$('script').value.length.toLocaleString()} / 20,000`);
async function generate() {
  if(currentJob)throw new Error('Generation is already running.');
  const result=await api('/generate',{method:'POST',body:{profile_id:$('generate-profile').value,text:$('script').value,temperature:Number($('temperature').value),exaggeration:Number($('exaggeration').value),cfg_weight:Number($('cfg').value),pause_ms:Number($('pause-ms').value)}});
  currentJob=result.id;$('generate-button').disabled=true;$('cancel-generation').disabled=false;$('generation-progress').hidden=false;
  try {
    while(currentJob) {
      const job=await api(`/jobs/${currentJob}`);$('generation-progress').max=job.total;$('generation-progress').value=job.completed;
      $('generation-state').textContent=`${job.status} · ${job.completed} / ${job.total} segments. CPU generation may take several minutes.`;
      if(job.status==='complete'){await refresh();showResult(job.asset);notify('AI-generated recording saved. Listen and evaluate its similarity.');break;}
      if(['failed','cancelled'].includes(job.status))throw new Error(job.error || job.status);
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
  } finally {currentJob=null;$('generate-button').disabled=false;$('cancel-generation').disabled=true;}
}
$('generate-button').addEventListener('click',protect(generate));$('regenerate').addEventListener('click',protect(generate));
$('cancel-generation').addEventListener('click',protect(async()=>{if(currentJob){const response=await api(`/jobs/${currentJob}/cancel`,{method:'POST'});notify(response.notice);}}));
function showResult(asset) {
  resultAsset=asset;$('generation-result').hidden=false;
  const reference=asset.metadata.reference_id || assets.find(a=>a.id===asset.metadata.source_asset)?.metadata.reference_id;
  const referenceAvailable=reference && assets.some(a=>a.id===reference);
  $('original-player').src=referenceAvailable?`/api/assets/${reference}/audio`:'';$('original-player').hidden=!referenceAvailable;
  $('generated-player').src=`/api/assets/${asset.id}/audio`;
  $('generated-wav').href=`/api/assets/${asset.id}/export/wav`;$('generated-mp3').href=`/api/assets/${asset.id}/export/mp3`;
  $('review-form').reset();show('generate');
}
function stopAudio(player){player.pause();player.currentTime=0;}
$('generated-stop').addEventListener('click',()=>stopAudio($('generated-player')));
$('generated-replay').addEventListener('click',protect(async()=>{stopAudio($('generated-player'));await $('generated-player').play();}));
['similarity','naturalness','pronunciation','clarity','consistency'].forEach(key=>{const label=document.createElement('label');label.textContent=key[0].toUpperCase()+key.slice(1);const select=document.createElement('select');select.id='rating-'+key;[1,2,3,4,5].forEach(n=>{const option=document.createElement('option');option.value=n;option.textContent=n;select.append(option);});select.value=3;label.append(select);$('rating-controls').append(label);});
$('review-form').addEventListener('submit',protect(async event=>{event.preventDefault();if(!resultAsset)return;const body={notes:$('review-notes').value};['similarity','naturalness','pronunciation','clarity','consistency'].forEach(key=>body[key]=Number($('rating-'+key).value));await api(`/assets/${resultAsset.id}/review`,{method:'POST',body});await renderReviews();notify('Your quality evaluation was saved.');}));
async function renderReviews(){const reviews=await api('/reviews');$('reviews-list').replaceChildren();if(!reviews.length){$('reviews-list').innerHTML='<p class="empty">No evaluations yet. Compare generated and reference clips in Generate Speech.</p>';return;}reviews.forEach(r=>{const div=document.createElement('div');div.className='asset-row';const a=assets.find(a=>a.id===r.asset_id);div.innerHTML=`<div class="asset-info"><strong>${escapeText(a?.name || r.asset_id)}</strong><small>${escapeText(a?.metadata.engine)} · Similarity ${r.data.similarity}/5 · Naturalness ${r.data.naturalness}/5 · Pronunciation ${r.data.pronunciation}/5 · Clarity ${r.data.clarity}/5 · Consistency ${r.data.consistency}/5</small><p class="footnote">${escapeText(r.data.notes)}</p></div>`;$('reviews-list').append(div);});}
$('export-reviews').addEventListener('click',protect(async()=>{const blob=new Blob([JSON.stringify({assets:assets.filter(a=>a.kind==='generated'),reviews:await api('/reviews')},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='voice-quality-evaluations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}));
function drawWave(canvas,peaks) {const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.strokeStyle='#d4ed90';ctx.lineWidth=1.5;ctx.beginPath();peaks.forEach((peak,i)=>{const x=i/peaks.length*canvas.width;const height=Math.max(1,peak*canvas.height*.45);ctx.moveTo(x,canvas.height/2-height);ctx.lineTo(x,canvas.height/2+height);});ctx.stroke();}
async function editorSelection(){const id=$('edit-asset').value;if(!id){$('edit-player').removeAttribute('src');drawWave($('edit-wave'),[]);return;}const wave=await api(`/assets/${id}/waveform`);drawWave($('edit-wave'),wave.peaks);$('trim-start').value=0;$('trim-end').value=wave.seconds.toFixed(3);$('edit-player').src=`/api/assets/${id}/audio`;$('edit-wav').href=`/api/assets/${id}/export/wav`;$('edit-mp3').href=`/api/assets/${id}/export/mp3`;}
$('edit-asset').addEventListener('change',protect(editorSelection));$('edit-stop').addEventListener('click',()=>stopAudio($('edit-player')));
$('apply-edit').addEventListener('click',protect(async()=>{const id=$('edit-asset').value;if(!id)throw new Error('Choose a recording first.');$('apply-edit').disabled=true;try{const result=await api(`/assets/${id}/edit`,{method:'POST',body:{start:Number($('trim-start').value),end:Number($('trim-end').value),speed:Number($('edit-speed').value),pitch:Number($('edit-pitch').value),remove_silence:$('silence-remove').checked,denoise:$('denoise').checked}});await refresh();$('edit-asset').value=result.id;await editorSelection();notify('Edited copy saved; original unchanged. Select “Use reference” in the library if you want to use it for cloning.');}finally{$('apply-edit').disabled=false;}}));
async function engineSummary(){const status=await api('/engine');const missing=status.models[settings.engine]?.missing || [];const ready=status.loaded===settings.engine;$('engine-badge').textContent=ready?'READY':missing.length?'MODEL MISSING':'NOT LOADED';$('engine-summary').textContent=!status.package_version?'Voice engine package is missing. Run Install or Repair.cmd.':missing.length?'Download the selected model using Download Models.cmd.':status.message;$('engine-message').textContent=status.message;}
async function diagnostics(){const result=await api('/diagnostics');$('diagnostics').textContent=JSON.stringify(result,null,2);await engineSummary();}
$('refresh-diagnostics').addEventListener('click',protect(diagnostics));
$('load-engine').addEventListener('click',protect(async()=>{await api('/engine/load',{method:'POST'});$('load-engine').disabled=true;try{let status;do{await new Promise(resolve=>setTimeout(resolve,1000));status=await api('/engine');$('engine-message').textContent=status.message;}while(status.busy);await diagnostics();notify(status.message,status.loaded!==settings.engine);}finally{$('load-engine').disabled=false;}}));
$('shutdown').addEventListener('click',protect(async()=>{if(recorder && recorder.state!=='inactive')throw new Error('Stop and save your recording before shutting down.');await api('/shutdown',{method:'POST'});notify('Studio is shutting down. You can close this browser tab.');}));
async function listMicrophones(){const devices=await navigator.mediaDevices.enumerateDevices();const selected=$('microphone').value;$('microphone').replaceChildren();const def=document.createElement('option');def.value='';def.textContent='System default';$('microphone').append(def);devices.filter(d=>d.kind==='audioinput').forEach((device,i)=>{const opt=document.createElement('option');opt.value=device.deviceId;opt.textContent=device.label||`Microphone ${i+1}`;$('microphone').append(opt);});if([...$('microphone').options].some(o=>o.value===selected))$('microphone').value=selected;}
async function getMicrophone(){if(!navigator.mediaDevices?.getUserMedia)throw new Error('Microphone access needs a supported browser at the loopback address. Use current Chrome or Edge.');return navigator.mediaDevices.getUserMedia({audio:{deviceId:$('microphone').value?{exact:$('microphone').value}:undefined,echoCancellation:false,noiseSuppression:false,autoGainControl:false}});}
$('microphone-enable').addEventListener('click',protect(async()=>{const temporary=await getMicrophone();try{await listMicrophones();notify('Microphone permission granted. Select your device and start recording.');}finally{temporary.getTracks().forEach(t=>t.stop());}}));
function liveMeter(){if(!analyser)return;const values=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(values);const peaks=[];let total=0;for(let i=0;i<values.length;i++){const sample=(values[i]-128)/128;total+=sample*sample;if(i%4===0)peaks.push(Math.abs(sample));}const rms=Math.sqrt(total/values.length);$('input-level').style.width=Math.min(100,rms*350)+'%';$('level-label').textContent=`Input level ${Math.round(20*Math.log10(Math.max(rms,.00001)))} dBFS`;drawWave($('live-wave'),peaks);animation=requestAnimationFrame(liveMeter);}
function timer(){const elapsed=Math.floor(((pauseStarted||performance.now())-startedAt-pausedMs)/1000);$('timer').textContent=`${String(Math.floor(elapsed/60)).padStart(2,'0')}:${String(elapsed%60).padStart(2,'0')}`;if(elapsed>=600 && recorder?.state!=='inactive')recorder.stop();}
async function releaseMic(){cancelAnimationFrame(animation);clearInterval(timerHandle);stream?.getTracks().forEach(t=>t.stop());stream=null;analyser=null;if(context){await context.close();context=null;}$('input-level').style.width='0';}
$('record-start').addEventListener('click',protect(async()=>{
  $('record-start').disabled=true;
  try{
    if(typeof MediaRecorder==='undefined')throw new Error('This browser cannot record audio. Use current Chrome or Edge.');
    stream=await getMicrophone();await listMicrophones();recordingProfile=$('record-profile').value;chunks=[];recordedBlob=null;$('record-save').disabled=true;$('record-preview').hidden=true;
    recordingMime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
    recorder=new MediaRecorder(stream,recordingMime?{mimeType:recordingMime}:{});
    recorder.ondataavailable=event=>{if(event.data.size)chunks.push(event.data);};
    recorder.onerror=event=>{notify(event.error?.message || 'Microphone recording failed.',true);if(recorder.state!=='inactive')recorder.stop();};
    recorder.onstop=async()=>{
      recordedBlob=new Blob(chunks,{type:recorder.mimeType});if(recordedUrl)URL.revokeObjectURL(recordedUrl);recordedUrl=URL.createObjectURL(recordedBlob);$('record-preview').src=recordedUrl;$('record-preview').hidden=false;
      await releaseMic();$('record-start').disabled=false;$('record-pause').disabled=true;$('record-stop').disabled=true;$('record-save').disabled=!recordedBlob.size;$('microphone').disabled=false;$('record-profile').disabled=false;$('record-state').textContent='REVIEW YOUR RECORDING';
    };
    context=new AudioContext();await context.resume();analyser=context.createAnalyser();analyser.fftSize=1024;context.createMediaStreamSource(stream).connect(analyser);
    startedAt=performance.now();pauseStarted=null;pausedMs=0;recorder.start(1000);timerHandle=setInterval(timer,200);liveMeter();
    $('record-pause').disabled=false;$('record-pause').textContent='Pause';$('record-stop').disabled=false;$('microphone').disabled=true;$('record-profile').disabled=true;$('record-state').textContent='RECORDING';
  }catch(error){await releaseMic();$('record-start').disabled=false;throw error;}
}));
$('record-pause').addEventListener('click',()=>{if(!recorder)return;if(recorder.state==='recording'){recorder.pause();pauseStarted=performance.now();$('record-pause').textContent='Resume';$('record-state').textContent='PAUSED';}else if(recorder.state==='paused'){pausedMs+=performance.now()-pauseStarted;pauseStarted=null;recorder.resume();$('record-pause').textContent='Pause';$('record-state').textContent='RECORDING';}});
$('record-stop').addEventListener('click',()=>{if(recorder?.state!=='inactive'){timer();recorder.stop();$('record-stop').disabled=true;$('record-pause').disabled=true;}});
$('record-save').addEventListener('click',protect(async()=>{if(!recordedBlob)throw new Error('Record audio first.');const extension=recordedBlob.type.includes('mp4')?'m4a':recordedBlob.type.includes('ogg')?'ogg':'webm';const file=new File([recordedBlob],`Microphone recording.${extension}`,{type:recordedBlob.type});await uploadReference(recordingProfile,file,$('record-consent').checked);await refresh();$('record-save').disabled=true;}));
window.addEventListener('beforeunload',event=>{if((recorder && recorder.state!=='inactive')||currentJob){event.preventDefault();event.returnValue='';}});
(async()=>{try{token=(await api('/session')).token;await refresh();show(location.hash.slice(1)||'dashboard');}catch(error){notify(error.message,true);}})();
