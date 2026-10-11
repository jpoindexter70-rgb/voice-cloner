// Real audio processing controls, shared by recording, generation and saved-audio editing.
const toneControls=[
 ['warmth','Warmth / bass',-6,6,0.1,0,' dB'],
 ['brightness','Brightness / treble',-6,6,0.1,0,' dB'],
 ['softness','Softness / smoothing',0,100,1,0,'%'],
 ['clarity','Clarity / presence',0,100,1,0,'%']
];
const deliveryControls=[
 ['noise','Background-noise reduction',0,30,1,0,' dB'],
 ['pause','Pause between narration segments',0,2,.05,.2,' seconds'],
 ['temperature','Delivery variation',.1,1.5,.05,.8,''],
 ['expression','Expressiveness · Original engine',0,1.5,.05,.5,''],
 ['similarity','Reference guidance · Original engine',0,1,.05,.5,'']
];
function toneValues(prefix){return Object.fromEntries(toneControls.map(([key])=>[key,Number($(prefix+'-'+key).value)]))}
function updateToneLabel(prefix,field){const [key,,_min,_max,_step,_value,unit]=field;$(prefix+'-'+key+'-value').textContent=Number($(prefix+'-'+key).value).toFixed(unit==='%'||unit===' dB'&&key==='noise'?0:2)+unit}
function addAdjustmentPanel(prefix,fields,before,title){
 const panel=document.createElement('section');panel.className='voice-adjustment-panel';const heading=document.createElement('h3');heading.textContent=title;panel.append(heading);
 const grid=document.createElement('div');grid.className='columns';panel.append(grid);before.before(panel);
 for(const field of fields){const [key,name,min,max,step,value]=field,label=document.createElement('label');label.textContent=name+' ';const output=document.createElement('output');output.id=prefix+'-'+key+'-value';const input=document.createElement('input');Object.assign(input,{id:prefix+'-'+key,type:'range',min,max,step,value});label.append(output,input);grid.append(label);updateToneLabel(prefix,field);input.oninput=()=>{updateToneLabel(prefix,field);if(prefix==='edit')$('save-edit').disabled=true;if(prefix==='record'){$('save-record').disabled=true;$('record-adjustment-status').textContent='Preview these adjustments before saving.'}};if(prefix==='voice')input.onchange=()=>saveVoiceSettings().catch(error=>message(error.message));}
 const reset=document.createElement('button');reset.type='button';reset.textContent='Reset '+title;reset.onclick=async()=>{for(const field of fields){$(prefix+'-'+field[0]).value=field[5];$(prefix+'-'+field[0]).oninput()}if(prefix==='voice')try{await saveVoiceSettings()}catch(error){message(error.message)}};panel.append(reset);
 before.before(panel);return panel;
}
const narrationPanel=addAdjustmentPanel('voice',[...toneControls,...deliveryControls],$('script').closest('label'),'Additional Voice Adjustments');
const explanation=document.createElement('p');explanation.className='subtle';explanation.textContent='Warmth, brightness, softness and clarity process the audio. Added pauses apply between longer narration segments. Delivery variation changes generation randomness. Expressiveness and reference guidance require the Original engine; Turbo does not support those two controls.';narrationPanel.append(explanation);
addAdjustmentPanel('record',toneControls,$('preview-record-adjustments'),'Voice Tone');
addAdjustmentPanel('edit',toneControls,$('play-edit-original'),'Voice Tone');
const originalWorkingSettings=workingSettings;workingSettings=function(){return {...originalWorkingSettings(),...toneValues('voice'),denoise:Number($('voice-noise').value)>0,noise_strength:Number($('voice-noise').value),...Object.fromEntries(deliveryControls.filter(([key])=>key!=='noise').map(([key])=>[key,Number($('voice-'+key).value)]))}};
const originalRecordingAdjustments=recordingAdjustments;recordingAdjustments=function(){return {...originalRecordingAdjustments(),...toneValues('record')}};
const originalEditAdjustmentSettings=editSettings;editSettings=function(){return {...originalEditAdjustmentSettings(),...toneValues('edit')}};
function resetTone(prefix){for(const field of toneControls){$(prefix+'-'+field[0]).value=field[5];updateToneLabel(prefix,field)}}
const originalResetRecording=resetRecordingControls;resetRecordingControls=function(){originalResetRecording();resetTone('record')};
const originalToneEditReference=editReference;editReference=function(...args){originalToneEditReference(...args);resetTone('edit')};
const originalToneEditGenerated=editGenerated;editGenerated=function(...args){originalToneEditGenerated(...args);resetTone('edit')};
let toneStamp='';setInterval(()=>{
 const p=profiles.find(profile=>profile.id===selected),stamp=JSON.stringify([selected,p?.settings]);if(stamp===toneStamp)return;toneStamp=stamp;
 for(const field of [...toneControls,...deliveryControls]){const key=field[0],input=$('voice-'+key);if(document.activeElement!==input)input.value=key==='noise'?(p?.settings.denoise?p.settings.noise_strength:0):(p?.settings[key]??field[5]);input.disabled=!p||(['expression','similarity'].includes(key)&&p.settings.engine==='turbo');updateToneLabel('voice',field);}
},300);
