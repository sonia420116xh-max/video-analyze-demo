<template>
  <div class="analyze-page">
    <section class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">短视频爆款模式拆解</p>
          <h2>{{ pageTitle }}</h2>
        </div>

        <div class="tool-bar">
          <el-upload
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            :show-file-list="false"
            accept="video/*"
          >
            <el-button>上传视频</el-button>
          </el-upload>

          <el-select
            v-model="modelType"
            placeholder="选择模型"
            class="model-select"
            :disabled="modelOptions.length === 0"
          >
            <el-option
              v-for="option in modelOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>

          <el-button type="primary" @click="startAnalyze" :loading="loading" :disabled="!modelType">
            {{ loading ? '后台分析中' : '开始AI拆解' }}
          </el-button>
        </div>
      </header>

      <div class="file-strip" v-if="currentFileName">
        <span>当前视频</span>
        <strong>{{ currentFileName }}</strong>
      </div>

      <!-- <section class="job-panel" v-if="currentJobId">
        <div>
          <p class="eyebrow">分析任务</p>
          <strong>{{ jobStatusText }}</strong>
          <p>{{ jobMessage || '后台正在处理视频，完成后会自动展示结果并写入历史记录。' }}</p>
        </div>
        <el-button size="small" @click="pollJobStatus(currentJobId, true)" :loading="jobPolling">
          查看进度
        </el-button>
      </section> -->

      <section class="history-panel" v-if="historyLoading || historyList.length > 0 || historyError">
        <div class="history-head">
          <div>
            <p class="eyebrow">历史分析</p>
            <h3>已保存的视频拆解</h3>
          </div>
          <el-button size="small" @click="loadHistory" :loading="historyLoading">刷新</el-button>
        </div>

        <div class="history-list" v-if="historyList.length > 0">
          <article
            v-for="item in historyList"
            :key="item.id"
            class="history-card"
            :class="{ active: item.id === activeAnalysisId }"
            role="button"
            tabindex="0"
            @click="handleHistorySelect(item)"
            @keydown.enter.prevent="handleHistorySelect(item)"
            @keydown.space.prevent="handleHistorySelect(item)"
          >
            <span class="history-card-head">
              <span class="history-title">{{ item.filename }}</span>
              <el-button
                class="history-delete"
                size="small"
                type="danger"
                text
                @click.stop="confirmDeleteAnalysis(item)"
              >
                删除
              </el-button>
            </span>
            <span class="history-status-row">
              <el-tag
                size="small"
                :type="getAnalysisStatusTagType(item.id)"
                effect="plain"
              >
                {{ getAnalysisStatusText(item.id) }}
              </el-tag>
            </span>
            <span class="history-meta">
              {{ item.formula || '未识别模式' }} / {{ item.subtype || '待判断' }} · {{ item.shot_count || 0 }} 个分镜
            </span>
            <span class="history-time">{{ formatCreatedAt(item.created_at) }}</span>
          </article>
        </div>

        <div v-else class="history-empty">
          {{ historyLoading ? '正在加载历史记录...' : historyError || '暂无历史记录' }}
        </div>
      </section>

      <div class="analysis-shell">
        <aside class="video-panel">
          <video
            v-if="videoPreviewUrl"
            ref="videoRef"
            class="video-preview"
            :src="videoPreviewUrl"
            controls
            autoplay
            muted
            loop
            playsinline
          />
          <div v-else class="video-empty">
            <span>上传视频后左侧自动预览</span>
          </div>
        </aside>

        <main class="story-panel">
          <div v-if="isActiveReanalysisRunning" class="regenerating-banner">
            <span class="regenerating-spinner" />
            <strong>正在重新生成中</strong>
            <p>{{ jobMessage || '正在重新抽帧、转写并调用 AI 生成新的视频拆解结果。' }}</p>
          </div>

          <div v-if="resultList.length > 0" class="result-head">
            <div>
              <p class="eyebrow">爆款公式</p>
              <!-- <h3>{{ formulaName }} / {{ formulaSubtype }}</h3> -->
              <h3>{{ formulaName }}</h3>
              <div class="result-tags">
                <el-tag size="small" type="success">{{ formulaSubtype }}</el-tag>
                <el-tag v-if="currentAnalysisModel" size="small" type="info" effect="plain">
                  {{ currentAnalysisModel }}
                </el-tag>
              </div>
              <p class="category-reason" v-if="categoryReason">{{ categoryReason }}</p>
            </div>
            <div class="result-actions">
              <div class="result-count">{{ resultList.length }} 个分镜</div>
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!canReanalyze"
                :loading="reanalyzeLoading"
                @click="reanalyzeCurrent"
              >
                重新拆解
              </el-button>
            </div>
          </div>

          <div v-if="resultList.length > 0" class="story-list">
            <article
              class="story-item"
              v-for="(item, idx) in resultList"
              :key="`${idx}-${item.start_time}-${item.end_time}`"
              @click="seekToSegment(item)"
            >
              <img
                v-if="item.image_url"
                class="shot-thumb"
                :src="getImageUrl(item.image_url)"
                :alt="item.title || `分镜 ${idx + 1}`"
              />
              <div v-else class="shot-thumb shot-thumb-empty">{{ idx + 1 }}</div>

              <div class="shot-body">
                <div class="shot-meta">
                  <span class="time-pill">{{ formatTime(item.start_time) }} - {{ formatTime(item.end_time) }}</span>
                  <strong>{{ item.title || item.narrative_role || `分镜 ${idx + 1}` }}</strong>
                </div>

                <p class="scene-text">{{ item.scene_description }}</p>

                <blockquote class="script-text">
                  {{ item.script }}
                </blockquote>

                <div class="tags">
                  <!-- <el-tag size="small" type="success">{{ item.content_tag || '情感叙事' }}</el-tag>
                  <el-tag size="small" type="warning">{{ item.shot_type || '镜前特写' }}</el-tag>
                  <el-tag v-if="item.product_category" size="small" type="info">{{ item.product_category }}</el-tag>
                  <el-tag v-if="item.evidence_frame" size="small">{{ item.evidence_frame }}</el-tag>
                  <el-tag size="small">{{ item.visual_tactic || formulaName }}</el-tag> -->
                </div>
              </div>
            </article>
          </div>

          <div v-else class="empty-result">
            <h3>等待拆解结果</h3>
            <p>上传视频后，会先判断属于第一人称视角、开箱 / ASMR、GRWM + 产品、分屏对比或日常 Vlog，再按对应叙事套路生成分镜。</p>
          </div>
        </main>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const fileList = ref([])
const modelType = ref('gemini-2.5-pro')
const modelOptions = ref([])
const loading = ref(false)
const reanalyzeLoading = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const jobPolling = ref(false)
const currentJobId = ref('')
const jobStatus = ref('')
const jobMessage = ref('')
const resultList = ref([])
const historyList = ref([])
const videoPreviewUrl = ref('')
const isLocalPreview = ref(false)
const currentFileName = ref('')
const activeAnalysisId = ref('')
const currentAnalysisModel = ref('')
const reanalyzingAnalysisId = ref('')
const analysisStatusMap = ref({})
const analysisVersion = ref(Date.now())
const videoRef = ref(null)
let currentFile = null

const formulaName = computed(() => resultList.value[0]?.viral_formula || '自动识别模式')
const formulaSubtype = computed(() => resultList.value[0]?.formula_subtype || '自动识别小类')
const categoryReason = computed(() => resultList.value[0]?.category_reason || '')
const pageTitle = computed(() => {
  // if (resultList.value.length > 0) return `${formulaName.value} / ${formulaSubtype.value}`
  if (resultList.value.length > 0) return `${formulaName.value}`
  return '自动识别爆款公式'
})
const jobStatusText = computed(() => {
  const statusMap = {
    queued: '任务已提交',
    processing: '正在后台分析',
    completed: '分析完成',
    failed: '分析失败'
  }
  return statusMap[jobStatus.value] || '等待任务状态'
})
const canReanalyze = computed(() => Boolean(activeAnalysisId.value) && !loading.value && !reanalyzeLoading.value)
const isActiveReanalysisRunning = computed(() => {
  if (!activeAnalysisId.value) return false
  if (reanalyzingAnalysisId.value !== activeAnalysisId.value) return false
  return ['queued', 'processing'].includes(jobStatus.value)
})

const isModelAvailable = (value) => modelOptions.value.some((option) => option.value === value)

const setAnalysisStatus = (analysisId, status) => {
  if (!analysisId) return
  analysisStatusMap.value = {
    ...analysisStatusMap.value,
    [analysisId]: status,
  }
}

const getAnalysisStatus = (analysisId) => analysisStatusMap.value[analysisId] || 'completed'

const getAnalysisStatusText = (analysisId) => {
  const statusMap = {
    queued: '等待中',
    processing: '进行中',
    completed: '已完成',
    failed: '失败',
  }
  return statusMap[getAnalysisStatus(analysisId)] || '已完成'
}

const getAnalysisStatusTagType = (analysisId) => {
  const typeMap = {
    queued: 'warning',
    processing: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return typeMap[getAnalysisStatus(analysisId)] || 'success'
}

const normalizeJsonText = (text) => {
  if (typeof text !== 'string') return text

  let cleaned = text.trim()
  if (cleaned.startsWith('```')) {
    const lines = cleaned.split('\n')
    if (lines[0]?.startsWith('```')) lines.shift()
    if (lines[lines.length - 1]?.trim() === '```') lines.pop()
    cleaned = lines.join('\n').trim()
  }

  const arrayStart = cleaned.indexOf('[')
  const arrayEnd = cleaned.lastIndexOf(']')
  if (arrayStart !== -1 && arrayEnd !== -1 && arrayStart < arrayEnd) {
    return cleaned.slice(arrayStart, arrayEnd + 1).trim()
  }

  const objectStart = cleaned.indexOf('{')
  const objectEnd = cleaned.lastIndexOf('}')
  if (objectStart !== -1 && objectEnd !== -1 && objectStart < objectEnd) {
    return cleaned.slice(objectStart, objectEnd + 1).trim()
  }

  return cleaned
}

const toSeconds = (value) => {
  if (typeof value === 'number') return value
  if (!value) return 0
  const text = String(value).replace(',', '.')
  const number = Number(text)
  if (!Number.isNaN(number)) return number

  const parts = text.split(':').map(Number)
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return 0
}

const formatTime = (value) => {
  const seconds = toSeconds(value)
  const totalSeconds = Math.max(0, Math.round(seconds))
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const remainSeconds = String(totalSeconds % 60).padStart(2, '0')
  return `${minutes}:${remainSeconds}`
}

const getImageUrl = (url) => `${url}?v=${analysisVersion.value}`

const formatCreatedAt = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const setVideoPreview = (url, local = false) => {
  if (isLocalPreview.value && videoPreviewUrl.value) {
    URL.revokeObjectURL(videoPreviewUrl.value)
  }
  videoPreviewUrl.value = url
  isLocalPreview.value = local
}

const handleFileChange = (file) => {
  currentFile = file.raw
  currentFileName.value = file.name
  fileList.value = [file]
  resultList.value = []
  activeAnalysisId.value = ''
  clearJobState()

  setVideoPreview(URL.createObjectURL(file.raw), true)
}

const seekToSegment = (item) => {
  if (!videoRef.value) return
  videoRef.value.currentTime = toSeconds(item.start_time)
  videoRef.value.play().catch(() => {})
}

const startAnalyze = async () => {
  if (!currentFile) {
    ElMessage.warning('请上传视频')
    return
  }
  if (!modelType.value) {
    ElMessage.warning('当前没有可用模型，请先在后端配置对应 API Key')
    return
  }

  loading.value = true
  const fd = new FormData()
  fd.append('file', currentFile)
  fd.append('model', modelType.value)
  fd.append('async_mode', 'true')

  try {
    const res = await axios.post('/api/analyze', fd, { timeout: 60000 })
    currentJobId.value = res.data.job_id || ''
    jobStatus.value = res.data.status || 'queued'
    jobMessage.value = res.data.msg || '任务已提交，后台分析中'
    if (!currentJobId.value) throw new Error('后端未返回任务ID')
    localStorage.setItem('videoAnalyzePendingJobId', currentJobId.value)
    ElMessage.success('任务已提交，可以等待完成或稍后刷新查看历史')
    scheduleJobPolling(currentJobId.value, 1200)
  } catch (err) {
    console.error('analyze failed:', err)
    const detail = err?.response?.data?.detail || err?.response?.data?.msg || err?.message
    ElMessage.error(detail ? `解析失败：${detail}` : '解析失败')
    loading.value = false
    clearJobState()
  }
}

const reanalyzeCurrent = async () => {
  if (!activeAnalysisId.value) {
    ElMessage.warning('请先选择一条已保存的视频拆解')
    return
  }
  if (!modelType.value) {
    ElMessage.warning('当前没有可用模型，请先在后端配置对应 API Key')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定重新拆解「${currentFileName.value || '当前视频'}」吗？确认后会重新生成分镜结果，并替换当前历史记录。`,
      '重新拆解确认',
      {
        confirmButtonText: '确认重新拆解',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  const targetAnalysisId = activeAnalysisId.value
  reanalyzeLoading.value = true
  loading.value = true
  reanalyzingAnalysisId.value = targetAnalysisId
  jobStatus.value = 'queued'
  jobMessage.value = '重新拆解任务已提交，后台分析中'
  setAnalysisStatus(targetAnalysisId, 'queued')
  try {
    clearJobState()
    reanalyzingAnalysisId.value = targetAnalysisId
    jobStatus.value = 'queued'
    jobMessage.value = '重新拆解任务已提交，后台分析中'
    setAnalysisStatus(targetAnalysisId, 'queued')
    const fd = new FormData()
    fd.append('model', modelType.value)
    const res = await axios.post(`/api/analyses/${targetAnalysisId}/reanalyze`, fd, { timeout: 60000 })
    currentJobId.value = res.data.job_id || ''
    jobStatus.value = res.data.status || 'queued'
    jobMessage.value = res.data.msg || '重新拆解任务已提交，后台分析中'
    if (!currentJobId.value) throw new Error('后端未返回任务ID')
    localStorage.setItem('videoAnalyzePendingJobId', currentJobId.value)
    ElMessage.success('已提交重新拆解任务，完成后会替换当前结果')
    scheduleJobPolling(currentJobId.value, 1200)
  } catch (err) {
    console.error('reanalyze failed:', err)
    const detail = err?.response?.data?.detail || err?.response?.data?.msg || err?.message
    ElMessage.error(detail ? `重新拆解失败：${detail}` : '重新拆解失败')
    loading.value = false
    reanalyzingAnalysisId.value = ''
    setAnalysisStatus(targetAnalysisId, 'failed')
    clearJobState()
  } finally {
    reanalyzeLoading.value = false
  }
}

const clearJobState = () => {
  currentJobId.value = ''
  jobStatus.value = ''
  jobMessage.value = ''
  localStorage.removeItem('videoAnalyzePendingJobId')
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

let pollTimer = null

const scheduleJobPolling = (jobId, delay = 2500) => {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = window.setTimeout(() => {
    pollJobStatus(jobId)
  }, delay)
}

const pollJobStatus = async (jobId, manual = false) => {
  if (!jobId) return
  jobPolling.value = true
  try {
    const res = await axios.get(`/api/analysis-jobs/${jobId}`, { timeout: 10000 })
    const job = res.data.data
    currentJobId.value = job.job_id
    jobStatus.value = job.status
    jobMessage.value = job.message || ''
    currentFileName.value = job.filename || currentFileName.value
    const affectedAnalysisId = job.replace_analysis_id || job.analysis_id || reanalyzingAnalysisId.value
    if (affectedAnalysisId && ['queued', 'processing', 'completed', 'failed'].includes(job.status)) {
      setAnalysisStatus(affectedAnalysisId, job.status)
      if (job.replace_analysis_id) reanalyzingAnalysisId.value = job.replace_analysis_id
    }

    if (job.status === 'completed') {
      resultList.value = JSON.parse(normalizeJsonText(job.data || '[]'))
      activeAnalysisId.value = job.analysis_id || ''
      currentAnalysisModel.value = job.model || modelType.value || ''
      setAnalysisStatus(activeAnalysisId.value, 'completed')
      reanalyzingAnalysisId.value = ''
      if (job.video_url) setVideoPreview(job.video_url, false)
      analysisVersion.value = Date.now()
      loading.value = false
      await loadHistory()
      clearJobState()
      ElMessage.success('拆解完成！')
      return
    }

    if (job.status === 'failed') {
      loading.value = false
      setAnalysisStatus(affectedAnalysisId, 'failed')
      reanalyzingAnalysisId.value = ''
      clearJobState()
      ElMessage.error(job.message ? `分析失败：${job.message}` : '分析失败')
      return
    }

    loading.value = true
    scheduleJobPolling(jobId)
    if (manual) ElMessage.info(job.message || '后台分析中')
  } catch (err) {
    console.error('poll job failed:', err)
    if (err?.response?.status === 404) {
      loading.value = false
      clearJobState()
      ElMessage.warning('后台任务状态不存在，可能后端重启过；已完成的结果可在历史记录中查看')
      await loadHistory()
      return
    }
    if (manual) {
      const detail = err?.response?.data?.detail || err?.message
      ElMessage.error(detail ? `任务查询失败：${detail}` : '任务查询失败')
    }
    scheduleJobPolling(jobId, 5000)
  } finally {
    jobPolling.value = false
  }
}

const loadHistory = async () => {
  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await axios.get('/api/analyses', { timeout: 10000 })
    historyList.value = res.data.data || []
  } catch (err) {
    console.error('load history failed:', err)
    historyError.value = '历史记录加载失败，请确认后端服务已启动且未被分析任务卡住'
    ElMessage.error('历史记录加载失败')
  } finally {
    historyLoading.value = false
  }
}

const loadModelOptions = async () => {
  try {
    const res = await axios.get('/api/model-options', { timeout: 10000 })
    modelOptions.value = res.data.data || []
    if (!isModelAvailable(modelType.value)) {
      modelType.value = modelOptions.value[0]?.value || ''
    }
  } catch (err) {
    console.error('load model options failed:', err)
    modelOptions.value = []
    modelType.value = ''
    ElMessage.error('模型配置加载失败，请确认后端服务已启动')
  }
}

const loadAnalysis = async (id) => {
  if (!id) return
  if (['queued', 'processing'].includes(getAnalysisStatus(id))) {
    ElMessage.info('该视频正在重新生成中，请稍后查看')
    return
  }
  try {
    clearJobState()
    loading.value = false
    const res = await axios.get(`/api/analyses/${id}`, { timeout: 10000 })
    const detail = res.data.data
    resultList.value = detail.data || []
    currentFileName.value = detail.filename || ''
    activeAnalysisId.value = detail.id
    currentAnalysisModel.value = detail.model || ''
    if (detail.model && isModelAvailable(detail.model)) {
      modelType.value = detail.model
    }
    currentFile = null
    fileList.value = []
    setVideoPreview(detail.video_url || '', false)
    analysisVersion.value = Date.now()
  } catch (err) {
    console.error('load analysis failed:', err)
    const detail = err?.response?.data?.detail || err?.message
    ElMessage.error(detail ? `记录加载失败：${detail}` : '记录加载失败')
  }
}

const handleHistorySelect = (item) => {
  if (!item?.id) return
  loadAnalysis(item.id)
}

const clearCurrentAnalysis = () => {
  resultList.value = []
  activeAnalysisId.value = ''
  currentAnalysisModel.value = ''
  currentFileName.value = ''
  currentFile = null
  fileList.value = []
  setVideoPreview('', false)
  analysisVersion.value = Date.now()
}

const confirmDeleteAnalysis = async (item) => {
  if (!item?.id) return

  try {
    await ElMessageBox.confirm(
      `确定删除「${item.filename || '这条视频拆解'}」吗？删除后该视频、分镜图片和拆解结果都会移除。`,
      '删除拆解记录',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  try {
    await axios.delete(`/api/analyses/${item.id}`, { timeout: 10000 })
    if (item.id === activeAnalysisId.value) {
      clearJobState()
      loading.value = false
      clearCurrentAnalysis()
    }
    await loadHistory()
    ElMessage.success('已删除拆解记录')
  } catch (err) {
    console.error('delete analysis failed:', err)
    const detail = err?.response?.data?.detail || err?.message
    ElMessage.error(detail ? `删除失败：${detail}` : '删除失败')
  }
}

onMounted(() => {
  loadModelOptions()
  loadHistory()
  const pendingJobId = localStorage.getItem('videoAnalyzePendingJobId')
  if (pendingJobId) {
    currentJobId.value = pendingJobId
    jobStatus.value = 'processing'
    jobMessage.value = '正在恢复后台任务状态'
    loading.value = true
    pollJobStatus(pendingJobId)
  }
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
  if (isLocalPreview.value && videoPreviewUrl.value) URL.revokeObjectURL(videoPreviewUrl.value)
})
</script>

<style scoped>
.analyze-page {
  min-height: 100vh;
  padding: 24px;
  background:
    linear-gradient(180deg, rgba(247, 248, 252, 0.96), rgba(239, 243, 248, 0.96)),
    repeating-linear-gradient(90deg, rgba(20, 31, 45, 0.04) 0, rgba(20, 31, 45, 0.04) 1px, transparent 1px, transparent 84px);
  color: #172033;
}

.workspace {
  max-width: 1480px;
  margin: 0 auto;
}

.topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #d9e1ec;
}

.topbar h2,
.result-head h3,
.history-head h3,
.empty-result h3 {
  margin: 0;
  font-size: 24px;
  line-height: 1.25;
}

.eyebrow {
  margin: 0 0 6px;
  color: #667085;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

.tool-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.model-select {
  width: 220px;
}

.file-strip {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 14px 0;
  color: #667085;
  font-size: 14px;
}

.file-strip strong {
  color: #263245;
}

.job-panel {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin: 0 0 16px;
  padding: 14px;
  background: #f0f7ff;
  border: 1px solid #b9d7f8;
  border-radius: 10px;
}

.job-panel strong {
  color: #174a7c;
}

.job-panel p:last-child {
  margin: 6px 0 0;
  color: #52657a;
  line-height: 1.55;
}

.history-panel {
  margin: 0 0 16px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid #dfe6f0;
  border-radius: 10px;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
}

.history-head h3 {
  font-size: 18px;
}

.history-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  column-gap: 10px;
  row-gap: 16px;
}

.history-card {
  display: grid;
  gap: 5px;
  box-sizing: border-box;
  min-width: 0;
  padding: 12px;
  text-align: left;
  color: #263245;
  background: #f8fafc;
  border: 1px solid #e1e8f2;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.history-card:hover,
.history-card:focus-visible,
.history-card.active {
  background: #ffffff;
  border-color: #7bb2f3;
}

.history-card:focus-visible {
  outline: 2px solid rgba(67, 126, 247, 0.26);
  outline-offset: 2px;
}

.history-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}

.history-card-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.history-status-row {
  display: flex;
  min-height: 24px;
  align-items: center;
}

.history-delete {
  opacity: 0;
  transition: opacity 0.16s ease;
}

.history-card:hover .history-delete,
.history-card:focus-visible .history-delete,
.history-card.active .history-delete {
  opacity: 1;
}

.history-meta,
.history-time {
  color: #667085;
  font-size: 12px;
  line-height: 1.45;
}

.history-meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-empty {
  padding: 10px 12px;
  color: #667085;
  background: #f8fafc;
  border: 1px dashed #d9e1ec;
  border-radius: 8px;
  font-size: 13px;
}

.analysis-shell {
  display: grid;
  grid-template-columns: minmax(320px, 0.86fr) minmax(520px, 1.14fr);
  gap: 22px;
  align-items: start;
}

.video-panel {
  position: sticky;
  top: 20px;
  min-height: 620px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0e1118;
  border: 1px solid #242a35;
  border-radius: 8px;
  overflow: hidden;
}

.video-preview {
  width: 100%;
  height: min(78vh, 860px);
  object-fit: contain;
  background: #0e1118;
}

.video-empty {
  display: grid;
  place-items: center;
  width: 100%;
  min-height: 620px;
  color: #98a2b3;
  font-size: 15px;
}

.story-panel {
  position: relative;
  min-height: 620px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #dfe6f0;
  border-radius: 8px;
  padding: 20px;
  backdrop-filter: blur(10px);
}

.regenerating-banner {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 14px;
  color: #475467;
  background: #f0f7ff;
  border: 1px solid #b9d7f8;
  border-radius: 8px;
}

.regenerating-banner strong {
  color: #174a7c;
  font-size: 14px;
}

.regenerating-banner p {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.regenerating-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #b9d7f8;
  border-top-color: #2b7de9;
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.result-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
}

.result-count {
  color: #667085;
  font-size: 14px;
  white-space: nowrap;
}

.result-tags {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 8px;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.category-reason {
  margin: 8px 0 0;
  color: #667085;
  line-height: 1.6;
  font-size: 13px;
}

.story-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.story-item {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid #e5ebf3;
  cursor: pointer;
}

.story-item:first-child {
  border-top: 0;
  padding-top: 0;
}

.shot-thumb {
  width: 56px;
  aspect-ratio: 7 / 10;
  object-fit: cover;
  border-radius: 8px;
  background: #edf1f7;
  border: 1px solid #dde5ef;
}

.shot-thumb-empty {
  display: grid;
  place-items: center;
  color: #667085;
  font-weight: 700;
}

.shot-body {
  min-width: 0;
}

.shot-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.time-pill {
  padding: 4px 9px;
  border-radius: 999px;
  background: #eef2f7;
  color: #667085;
  font-size: 13px;
  font-weight: 700;
}

.scene-text {
  margin: 0 0 10px;
  color: #344054;
  line-height: 1.65;
  font-size: 12px;
}

.script-text {
  margin: 0 0 12px;
  padding: 8px 12px;
  background: #fffaf0;
  border-left: 3px solid #f2b94b;
  color: #5f5140;
  line-height: 1.65;
  font-size: 12px;
}

.tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-result {
  display: grid;
  align-content: center;
  min-height: 560px;
  text-align: center;
  color: #667085;
}

.empty-result p {
  max-width: 560px;
  margin: 12px auto 0;
  line-height: 1.7;
}

@media (max-width: 980px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .tool-bar {
    justify-content: flex-start;
  }

  .analysis-shell {
    grid-template-columns: 1fr;
  }

  .video-panel {
    position: static;
    min-height: 420px;
  }

  .video-preview,
  .video-empty {
    height: 520px;
    min-height: 420px;
  }
}

@media (max-width: 640px) {
  .analyze-page {
    padding: 14px;
  }

  .model-select {
    width: 100%;
  }

  .tool-bar {
    width: 100%;
  }

  .story-panel {
    padding: 14px;
  }

  .story-item {
    grid-template-columns: 84px minmax(0, 1fr);
  }

  .shot-thumb {
    width: 84px;
  }
}
</style>
