<template>
  <div class="analyze-page">
    <section class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">短视频爆款模式拆解</p>
          <h2>{{ pageTitle }}</h2>
        </div>

        <div class="tool-bar">
          <el-input
            v-model="videoUrlInput"
            class="video-url-input"
            clearable
            placeholder="粘贴 TikTok / Instagram / YouTube 视频链接"
            @keyup.enter="startAnalyze"
          />
          <el-upload
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            :show-file-list="false"
            accept="video/*"
          >
            <el-button>上传视频</el-button>
          </el-upload>

          <!-- <el-select
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
          </el-select> -->

          <!-- <el-segmented
            v-model="breakdownGranularity"
            class="granularity-control"
            :options="granularityOptions"
          /> -->

          <el-button type="primary" @click="startAnalyze" :loading="loading" :disabled="!modelType">
            {{ loading ? '后台分析中' : '开始AI拆解' }}
          </el-button>
          <!-- <el-button
            v-if="canCancelJob"
            type="danger"
            plain
            @click="cancelCurrentJob"
          >
            停止生成
          </el-button> -->
        </div>
      </header>

      <div class="file-strip" v-if="currentFileName">
        <span>当前视频</span>
        <strong>{{ currentFileName }}</strong>
      </div>

      <div class="file-strip" v-else-if="videoUrlInput.trim()">
        <span>视频链接</span>
        <strong>{{ videoUrlInput.trim() }}</strong>
      </div>

      <section class="manual-transcript-panel">
        <div>
          <p class="eyebrow">手动字幕</p>
          <h3>ASR 兜底输入</h3>
        </div>
        <el-input
          v-model="manualTranscript"
          type="textarea"
          :rows="4"
          resize="vertical"
          placeholder="可选：粘贴 0.00 --> 3.08 ... 格式的口播字幕；填写后本次分析会跳过自动 ASR。"
        />
      </section>

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
          <div class="history-actions">
            <el-select
              v-model="selectedProductClassification"
              class="product-filter"
              size="small"
              placeholder="全部产品分类"
            >
              <el-option
                v-for="option in productClassificationOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-button size="small" @click="loadHistory" :loading="historyLoading">刷新</el-button>
          </div>
        </div>

        <div class="history-list" v-if="filteredHistoryList.length > 0">
          <article
            v-for="item in filteredHistoryList"
            :key="item.id"
            class="history-card"
            :class="{ active: item.id === activeAnalysisId }"
            role="button"
            tabindex="0"
            @click="handleHistorySelect(item)"
            @keydown.enter.prevent="handleHistorySelect(item)"
            @keydown.space.prevent="handleHistorySelect(item)"
          >
            <span class="history-cover">
              <img
                v-if="item.cover_url"
                :src="getImageUrl(item.cover_url)"
                :alt="item.filename || '视频封面'"
              />
              <span v-else-if="isPendingHistoryItem(item)" class="history-cover-empty">分析中</span>
              <span v-else class="history-cover-empty">无封面</span>
            </span>
            <span class="history-info">
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
                  :type="getHistoryItemStatusTagType(item)"
                  effect="plain"
                >
                  {{ getHistoryItemStatusText(item) }}
                </el-tag>
                <span v-if="isPendingHistoryItem(item)" class="history-job-message">
                  {{ item.message || '后台分析中' }}
                </span>
              </span>
              <span class="history-meta">
                {{ getHistoryItemMeta(item) }}
              </span>
              <span class="history-time">{{ formatCreatedAt(item.created_at) }}</span>
            </span>
          </article>
        </div>

        <div v-else class="history-empty">
          {{ historyLoading ? '正在加载历史记录...' : historyError || historyEmptyText }}
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

          <!-- <div v-if="analysisVersions.length > 1" class="version-toolbar">
            <span>模型结果</span>
            <el-checkbox-group v-model="selectedCompareModels" size="small" @change="handleCompareModelChange">
              <el-checkbox-button
                v-for="version in analysisVersions"
                :key="version.model"
                :label="version.model"
              >
                {{ version.model }}
              </el-checkbox-button>
            </el-checkbox-group>
          </div> -->

          <div v-if="currentDisplayItems.length > 0">
            <div class="model-result-grid" :class="{ 'compare-grid': isCompareMode }">
              <section
                v-for="version in visibleModelVersions"
                :key="version.model"
                class="model-result-card"
              >
                <div class="result-head">
                  <div class="result-title-block">
                    <div class="result-title-row">
                      <div>
                        <p class="eyebrow">爆款公式</p>
                        <h3 class="result-title">{{ getVersionFormulaName(version) }}</h3>
                      </div>
                      <div class="result-actions">
                        <div class="result-count">{{ version.shot_count || version.data?.length || 0 }} 个分镜</div>
                        <div class="reanalyze-controls">
                          <!-- <el-select
                            v-model="reanalyzeModelType"
                            size="small"
                            class="reanalyze-model-select"
                            placeholder="选择模型"
                            :disabled="modelOptions.length === 0"
                          >
                            <el-option
                              v-for="option in modelOptions"
                              :key="option.value"
                              :label="option.label"
                              :value="option.value"
                            />
                          </el-select> -->
                          <el-button
                            size="small"
                            type="primary"
                            plain
                            :disabled="!canReanalyzeModel(reanalyzeModelType)"
                            :loading="isReanalyzingModel(reanalyzeModelType)"
                            :title="getReanalyzeButtonTitle(reanalyzeModelType)"
                            @click="reanalyzeCurrent(reanalyzeModelType)"
                          >
                            重新拆解
                          </el-button>
                          <el-button
                            v-if="canStopReanalyzingModel(version.model)"
                            size="small"
                            type="danger"
                            plain
                            :loading="cancelingJob"
                            @click="confirmCancelCurrentJob(version.model)"
                          >
                            停止生成
                          </el-button>
                        </div>
                      </div>
                    </div>
                    <div class="result-tags">
                      <el-tag size="small" type="success">{{ getVersionFormulaSubtype(version) }}</el-tag>
                      <el-tag v-if="getVersionSellingPoint(version)" size="small" type="warning" effect="plain">
                        卖点角度 {{ getVersionSellingPoint(version) }}
                      </el-tag>
                      <el-tag v-if="getVersionGolden3s(version)" size="small" type="danger" effect="plain">
                        黄金3秒 {{ getVersionGolden3s(version) }}
                      </el-tag>
                      <!-- <el-tag v-if="version.model" size="small" type="info" effect="plain">
                        {{ version.model }}
                      </el-tag> -->
                    </div>
                    <p class="category-reason" v-if="getVersionCategoryReason(version)">
                      {{ getVersionCategoryReason(version) }}
                    </p>
                  </div>
                </div>
                <div class="story-list" :class="{ compact: isCompareMode }">
                  <article
                    class="story-item"
                    v-for="(item, idx) in version.data || []"
                    :key="`${version.model}-${idx}-${item.start_time}-${item.end_time}`"
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
                      <div class="script-block">
                        <span class="script-label">脚本/字幕</span>
                        <blockquote class="script-text">{{ formatShotScript(item) }}</blockquote>
                      </div>
                    </div>
                  </article>
                </div>
              </section>
            </div>
          </div>

          <div v-else class="empty-result" :class="{ 'is-loading': isInitialAnalysisRunning }">
            <template v-if="isInitialAnalysisRunning">
              <span class="empty-result-spinner" aria-hidden="true" />
              <h3>正在拆解视频</h3>
              <p>{{ jobMessage || '正在抽帧、转写并调用 AI 生成分镜，请稍等。' }}</p>
            </template>
            <template v-else-if="isEmptyAnalysisResult">
              <h3>本次未生成分镜</h3>
              <p>这条记录后端保存的结果为空，可能是模型返回了空数组或输出解析失败。可以切换模型重新拆解一次。</p>
              <div class="empty-result-actions">
                <el-select
                  v-model="reanalyzeModelType"
                  size="small"
                  class="reanalyze-model-select"
                  placeholder="选择模型"
                  :disabled="modelOptions.length === 0"
                >
                  <el-option
                    v-for="option in modelOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-button
                  type="primary"
                  plain
                  :disabled="!canReanalyzeModel(reanalyzeModelType)"
                  :loading="isReanalyzingModel(reanalyzeModelType)"
                  @click="reanalyzeCurrent(reanalyzeModelType)"
                >
                  重新拆解
                </el-button>
              </div>
            </template>
            <template v-else>
              <h3>等待拆解结果</h3>
              <p>上传视频后，会先判断属于第一人称视角、开箱 / ASMR、GRWM + 产品、分屏对比或日常 Vlog，再按对应叙事套路生成分镜。</p>
            </template>
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
const cancelingJob = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const jobPolling = ref(false)
const currentJobId = ref('')
const jobStatus = ref('')
const jobMessage = ref('')
const resultList = ref([])
const analysisVersions = ref([])
const selectedCompareModels = ref([])
const historyList = ref([])
const selectedProductClassification = ref('')
const videoPreviewUrl = ref('')
const videoUrlInput = ref('')
const isLocalPreview = ref(false)
const currentFileName = ref('')
const activeAnalysisId = ref('')
const currentAnalysisModel = ref('')
const reanalyzeModelType = ref('')
const reanalyzingAnalysisId = ref('')
const reanalyzingModel = ref('')
const manualTranscript = ref('')
const breakdownGranularity = ref('balanced')
const analysisStatusMap = ref({})
const analysisVersion = ref(Date.now())
const videoRef = ref(null)
let currentFile = null

const granularityOptions = [
  { label: '粗略', value: 'coarse' },
  { label: '均衡', value: 'balanced' },
  { label: '精细', value: 'fine' },
]

const PRODUCT_CLASSIFICATIONS = [
  '家居用品',
  '厨房用品',
  '家纺布艺',
  '家电',
  '女装与女士内衣',
  '穆斯林时尚',
  '鞋靴',
  '美妆个护',
  '手机与数码',
  '电脑办公',
  '宠物用品',
  '母婴用品',
  '运动与户外',
  '玩具和爱好',
  '家具',
  '五金工具',
  '家装建材',
  '汽车与摩托车',
  '时尚配件',
  '食品饮料',
  '保健',
  '图书&杂志&音频',
  '儿童时尚',
  '男装与男士内衣',
  '箱包',
  '虚拟商品',
  '二手',
  '收藏品',
  '珠宝与衍生品',
  '票务与代金券',
]

const productClassificationOptions = [
  { label: '全部产品分类', value: '' },
  ...PRODUCT_CLASSIFICATIONS.map((classification) => ({
    label: classification,
    value: classification,
  })),
]

const PENDING_ANALYSIS_JOBS_KEY = 'videoAnalyzePendingAnalysisJobs'
const loadPendingAnalysisJobs = () => {
  try {
    return JSON.parse(localStorage.getItem(PENDING_ANALYSIS_JOBS_KEY) || '{}')
  } catch {
    return {}
  }
}
const pendingAnalysisJobs = ref(loadPendingAnalysisJobs())

const getVersionByModel = (model) => analysisVersions.value.find((version) => version.model === model)
const activeVersion = computed(() => getVersionByModel(currentAnalysisModel.value))
const selectedModelVersions = computed(() => selectedCompareModels.value
  .map((model) => getVersionByModel(model))
  .filter(Boolean))
const currentDisplayVersion = computed(() => selectedModelVersions.value[0] || activeVersion.value || null)
const isCompareMode = computed(() => selectedModelVersions.value.length >= 2)
const fallbackDisplayVersion = computed(() => {
  if (currentDisplayVersion.value) return currentDisplayVersion.value
  if (!resultList.value.length) return null
  return {
    model: currentAnalysisModel.value || '',
    data: resultList.value,
    shot_count: resultList.value.length,
  }
})
const currentDisplayItems = computed(() => fallbackDisplayVersion.value?.data || [])
const filteredHistoryList = computed(() => {
  if (!selectedProductClassification.value) return historyList.value
  return historyList.value.filter((item) => (
    !isPendingHistoryItem(item)
    && item.product_classification === selectedProductClassification.value
  ))
})
const historyEmptyText = computed(() => (
  selectedProductClassification.value
    ? '当前分类下暂无历史记录'
    : '暂无历史记录'
))
const visibleModelVersions = computed(() => {
  if (isCompareMode.value) return selectedModelVersions.value
  return fallbackDisplayVersion.value ? [fallbackDisplayVersion.value] : []
})
const formulaName = computed(() => getVersionFormulaName(fallbackDisplayVersion.value))
const pageTitle = computed(() => {
  // if (resultList.value.length > 0) return `${formulaName.value} / ${formulaSubtype.value}`
  if (currentDisplayItems.value.length > 0) return `${formulaName.value}`
  return '自动识别爆款公式'
})
const jobStatusText = computed(() => {
  if (jobStatus.value === 'canceled') return '已停止'
  const statusMap = {
    queued: '任务已提交',
    processing: '正在后台分析',
    completed: '分析完成',
    failed: '分析失败'
  }
  return statusMap[jobStatus.value] || '等待任务状态'
})
const canCancelJob = computed(() => Boolean(currentJobId.value) && ['queued', 'processing'].includes(jobStatus.value))
const isActiveReanalysisRunning = computed(() => {
  if (!activeAnalysisId.value) return false
  if (reanalyzingAnalysisId.value !== activeAnalysisId.value) return false
  return ['queued', 'processing'].includes(jobStatus.value)
})
const isInitialAnalysisRunning = computed(() => (
  loading.value
  && !activeAnalysisId.value
  && !reanalyzingAnalysisId.value
))
const isEmptyAnalysisResult = computed(() => (
  Boolean(activeAnalysisId.value)
  && !loading.value
  && currentDisplayItems.value.length === 0
))

const isModelAvailable = (value) => modelOptions.value.some((option) => option.value === value)
const canStopReanalyzingModel = (model) => (
  Boolean(model)
  && isActiveReanalysisRunning.value
  && reanalyzingModel.value === model
  && canCancelJob.value
)

const updateReanalyzeModelType = (preferredModel = '') => {
  const candidates = [
    preferredModel,
    currentAnalysisModel.value,
    modelOptions.value[0]?.value,
  ].filter(Boolean)
  reanalyzeModelType.value = candidates.find((model) => isModelAvailable(model)) || ''
}

const savePendingAnalysisJobs = () => {
  localStorage.setItem(PENDING_ANALYSIS_JOBS_KEY, JSON.stringify(pendingAnalysisJobs.value))
}

const rememberAnalysisJob = (analysisId, jobId) => {
  if (!analysisId || !jobId) return
  pendingAnalysisJobs.value = {
    ...pendingAnalysisJobs.value,
    [analysisId]: jobId,
  }
  savePendingAnalysisJobs()
}

const forgetAnalysisJob = (analysisId) => {
  if (!analysisId || !pendingAnalysisJobs.value[analysisId]) return
  const next = { ...pendingAnalysisJobs.value }
  delete next[analysisId]
  pendingAnalysisJobs.value = next
  savePendingAnalysisJobs()
}

const isRunningStatus = (status) => ['queued', 'processing'].includes(status)
const hasRunningInitialAnalysisJob = () => (
  Boolean(currentJobId.value)
  && isRunningStatus(jobStatus.value)
  && !reanalyzingAnalysisId.value
)

const getVersionFirstItem = (version) => version?.data?.[0] || null

const getVersionFormulaName = (version) => (
  version?.formula
  || getVersionFirstItem(version)?.viral_formula
  || '自动识别模式'
)

const getVersionFormulaSubtype = (version) => (
  version?.subtype
  || getVersionFirstItem(version)?.formula_subtype
  || '自动识别小类'
)

const getVersionCategoryReason = (version) => (
  version?.category_reason
  || getVersionFirstItem(version)?.category_reason
  || ''
)

const getVersionSellingPoint = (version) => formatSellingPoint(getVersionFirstItem(version))

const getVersionGolden3s = (version) => formatGolden3s(getVersionFirstItem(version))

const canReanalyzeModel = (model) => (
  Boolean(activeAnalysisId.value && model)
  && !loading.value
  && !reanalyzeLoading.value
  && isModelAvailable(model)
)

const isReanalyzingModel = (model) => reanalyzeLoading.value && reanalyzingModel.value === model

const getReanalyzeButtonTitle = (model) => {
  if (!model) return '请选择一个模型后再重新拆解'
  if (!isModelAvailable(model)) return `${model} 当前不可用，请先配置对应 API Key`
  return `使用 ${model} 重新拆解当前视频`
}

const setAnalysisStatus = (analysisId, status) => {
  if (!analysisId) return
  analysisStatusMap.value = {
    ...analysisStatusMap.value,
    [analysisId]: status,
  }
}

const getAnalysisStatus = (analysisId) => analysisStatusMap.value[analysisId] || 'completed'

const getAnalysisStatusText = (analysisId) => {
  if (getAnalysisStatus(analysisId) === 'canceled') return '已停止'
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
    canceled: 'info',
  }
  return typeMap[getAnalysisStatus(analysisId)] || 'success'
}

const isPendingHistoryItem = (item) => Boolean(item?.is_pending_job)

const getHistoryItemStatus = (item) => (
  isPendingHistoryItem(item)
    ? item.status || 'queued'
    : getAnalysisStatus(item.id)
)

const getHistoryItemStatusText = (item) => {
  if (!isPendingHistoryItem(item)) return getAnalysisStatusText(item.id)
  const statusMap = {
    queued: '等待中',
    processing: '进行中',
    failed: '失败',
    canceled: '已停止',
  }
  return statusMap[getHistoryItemStatus(item)] || '进行中'
}

const getHistoryItemStatusTagType = (item) => {
  if (!isPendingHistoryItem(item)) return getAnalysisStatusTagType(item.id)
  const typeMap = {
    queued: 'warning',
    processing: 'warning',
    failed: 'danger',
    canceled: 'info',
  }
  return typeMap[getHistoryItemStatus(item)] || 'warning'
}

const getHistoryItemMeta = (item) => {
  if (isPendingHistoryItem(item)) {
    return `${item.model || '未知模型'} · 分析完成后自动生成分镜`
  }
  const productClassification = item.product_classification || '未识别产品分类'
  return `${productClassification} · ${item.formula || '未识别模式'} / ${item.subtype || '待判断'} · ${item.shot_count || 0} 个分镜`
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

const formatShotScript = (item) => {
  const script = String(item?.script || '').trim()
  if (!script) return '该段无有效口播/字幕'
  if (/^画面[\/／、和与]字幕摘要\s*[:：]/.test(script) || /^画面摘要\s*[:：]/.test(script)) {
    return '该段无有效口播/字幕'
  }
  return script
}

const getImageUrl = (url) => `${url}?v=${analysisVersion.value}`

const formatTaxonomyLabel = (primary, subtype) => {
  if (!primary && !subtype) return ''
  if (!subtype || subtype === primary) return primary || subtype
  // return `${primary} · ${subtype}`
  return `${primary}`
}

const formatSellingPoint = (item) => {
  if (!item) return ''
  return formatTaxonomyLabel(item.selling_point_angle, item.selling_point_subtype)
}

const formatGolden3s = (item) => {
  if (!item) return ''
  return formatTaxonomyLabel(item.golden_3s_hook, item.golden_3s_subtype)
}

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
  videoUrlInput.value = ''
  fileList.value = [file]
  resultList.value = []
  analysisVersions.value = []
  selectedCompareModels.value = []
  activeAnalysisId.value = ''
  currentAnalysisModel.value = ''
  reanalyzeModelType.value = ''
  reanalyzingAnalysisId.value = ''
  reanalyzingModel.value = ''
  clearJobState()

  setVideoPreview(URL.createObjectURL(file.raw), true)
}

const applyAnalysisDetail = (detail) => {
  resultList.value = detail.data || []
  analysisVersions.value = detail.versions?.length
    ? detail.versions
    : [{
        model: detail.model || '',
        data: detail.data || [],
        shot_count: detail.data?.length || 0,
        is_active: true,
      }]
  currentFileName.value = detail.filename || ''
  activeAnalysisId.value = detail.id
  currentAnalysisModel.value = detail.model || ''
  updateReanalyzeModelType(detail.model || '')
  selectedCompareModels.value = detail.model ? [detail.model] : []
  currentFile = null
  fileList.value = []
  setVideoPreview(detail.video_url || '', false)
  analysisVersion.value = Date.now()
}

const handleCompareModelChange = (models) => {
  if (models.length === 0) {
    selectedCompareModels.value = currentAnalysisModel.value ? [currentAnalysisModel.value] : []
    return
  }
  if (models.length > 2) {
    selectedCompareModels.value = models.slice(-2)
  }
}

const seekToSegment = (item) => {
  if (!videoRef.value) return
  videoRef.value.currentTime = toSeconds(item.start_time)
  videoRef.value.play().catch(() => {})
}

const startAnalyze = async () => {
  const sourceVideoUrl = videoUrlInput.value.trim()
  if (!currentFile && !sourceVideoUrl) {
    ElMessage.warning('请上传视频，或粘贴 TikTok / Instagram / YouTube 视频链接')
    return
  }
  if (currentFile && sourceVideoUrl) {
    ElMessage.warning('请在上传视频和输入链接中选择一种方式')
    return
  }
  if (sourceVideoUrl && !/^https?:\/\//i.test(sourceVideoUrl)) {
    ElMessage.warning('视频链接需要以 http:// 或 https:// 开头')
    return
  }
  if (!currentFile && !sourceVideoUrl) {
    ElMessage.warning('请上传视频')
    return
  }
  if (!modelType.value) {
    ElMessage.warning('当前没有可用模型，请先在后端配置对应 API Key')
    return
  }

  loading.value = true
  const fd = new FormData()
  if (currentFile) fd.append('file', currentFile)
  if (sourceVideoUrl) fd.append('video_url', sourceVideoUrl)
  fd.append('model', modelType.value)
  fd.append('async_mode', 'true')
  fd.append('breakdown_granularity', breakdownGranularity.value)
  if (manualTranscript.value.trim()) fd.append('transcript_override', manualTranscript.value.trim())

  try {
    const res = await axios.post('/api/analyze', fd, { timeout: 60000 })
    currentJobId.value = res.data.job_id || ''
    jobStatus.value = res.data.status || 'queued'
    jobMessage.value = res.data.msg || '任务已提交，后台分析中'
    if (!currentJobId.value) throw new Error('后端未返回任务ID')
    localStorage.setItem('videoAnalyzePendingJobId', currentJobId.value)
    ElMessage.success('任务已提交，可以等待完成或稍后刷新查看历史')
    await loadHistory({ autoSelectFirst: false })
    scheduleJobPolling(currentJobId.value, 1200)
  } catch (err) {
    console.error('analyze failed:', err)
    const detail = err?.response?.data?.detail || err?.response?.data?.msg || err?.message
    ElMessage.error(detail ? `解析失败：${detail}` : '解析失败')
    if (sourceVideoUrl) {
      ElMessage.warning('如果链接下载失败，请下载到本地后使用“上传视频”手动上传解析')
    }
    loading.value = false
    clearJobState()
  }
}

const reanalyzeCurrent = async (model) => {
  if (!activeAnalysisId.value) {
    ElMessage.warning('请先选择一条已保存的视频拆解')
    return
  }
  const targetModel = model || reanalyzeModelType.value || currentAnalysisModel.value
  if (!targetModel) {
    ElMessage.warning('请选择一个模型后再重新拆解')
    return
  }
  if (!isModelAvailable(targetModel)) {
    ElMessage.warning(`${targetModel} 当前不可用，请先在后端配置对应 API Key`)
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定用 ${targetModel} 重新拆解「${currentFileName.value || '当前视频'}」吗？确认后会更新该模型的最新结果，并默认展示本次结果。`,
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
  reanalyzingModel.value = targetModel
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
    fd.append('model', targetModel)
    fd.append('breakdown_granularity', breakdownGranularity.value)
    if (manualTranscript.value.trim()) fd.append('transcript_override', manualTranscript.value.trim())
    const res = await axios.post(`/api/analyses/${targetAnalysisId}/reanalyze`, fd, { timeout: 60000 })
    currentJobId.value = res.data.job_id || ''
    jobStatus.value = res.data.status || 'queued'
    jobMessage.value = res.data.msg || '重新拆解任务已提交，后台分析中'
    if (!currentJobId.value) throw new Error('后端未返回任务ID')
    rememberAnalysisJob(targetAnalysisId, currentJobId.value)
    localStorage.setItem('videoAnalyzePendingJobId', currentJobId.value)
    ElMessage.success('已提交重新拆解任务，完成后会更新该模型版本')
    scheduleJobPolling(currentJobId.value, 1200)
  } catch (err) {
    console.error('reanalyze failed:', err)
    const detail = err?.response?.data?.detail || err?.response?.data?.msg || err?.message
    ElMessage.error(detail ? `重新拆解失败：${detail}` : '重新拆解失败')
    loading.value = false
    reanalyzingAnalysisId.value = ''
    reanalyzingModel.value = ''
    reanalyzeLoading.value = false
    setAnalysisStatus(targetAnalysisId, 'failed')
    clearJobState()
  }
}

const stopCurrentPolling = () => {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  currentJobId.value = ''
  jobStatus.value = ''
  jobMessage.value = ''
  loading.value = false
  reanalyzeLoading.value = false
  reanalyzingAnalysisId.value = ''
  reanalyzingModel.value = ''
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

const restoreCanceledReanalysisState = (analysisId) => {
  if (!analysisId) return
  if (reanalyzingAnalysisId.value === analysisId || activeAnalysisId.value === analysisId) {
    setAnalysisStatus(analysisId, 'completed')
  }
}

const cancelCurrentJob = async ({ skipConfirm = false, model = '' } = {}) => {
  if (!currentJobId.value) return
  if (!skipConfirm) {
    try {
      await ElMessageBox.confirm(
        model
          ? `确定停止 ${model} 的重新生成任务吗？停止后会保留当前已有的分析结果。`
          : '确定停止当前生成任务吗？停止后会保留当前已有的分析结果。',
        '停止生成确认',
        {
          confirmButtonText: '确认停止',
          cancelButtonText: '继续生成',
          type: 'warning',
        },
      )
    } catch {
      return
    }
  }
  const jobId = currentJobId.value
  cancelingJob.value = true
  try {
    const res = await axios.post(`/api/analysis-jobs/${jobId}/cancel`, null, { timeout: 10000 })
    const job = res.data.data || {}
    const affectedAnalysisId = job.replace_analysis_id || job.analysis_id || reanalyzingAnalysisId.value
    if (job.replace_analysis_id || reanalyzingAnalysisId.value) {
      restoreCanceledReanalysisState(affectedAnalysisId)
      forgetAnalysisJob(affectedAnalysisId)
    } else if (affectedAnalysisId) {
      setAnalysisStatus(affectedAnalysisId, 'canceled')
    }
    jobStatus.value = 'canceled'
    jobMessage.value = job.message || '已停止生成'
    loading.value = false
    reanalyzeLoading.value = false
    reanalyzingAnalysisId.value = ''
    reanalyzingModel.value = ''
    clearJobState()
    ElMessage.success('已停止生成')
  } catch (err) {
    console.error('cancel job failed:', err)
    const detail = err?.response?.data?.detail || err?.message
    ElMessage.error(detail ? `停止失败：${detail}` : '停止失败')
  } finally {
    cancelingJob.value = false
  }
}

const confirmCancelCurrentJob = (model = '') => cancelCurrentJob({ model })

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
    if (job.video_url && !videoPreviewUrl.value) {
      setVideoPreview(job.video_url, false)
    }
    const affectedAnalysisId = job.replace_analysis_id || job.analysis_id || reanalyzingAnalysisId.value
    if (affectedAnalysisId && ['queued', 'processing', 'completed', 'failed', 'canceled'].includes(job.status)) {
      setAnalysisStatus(affectedAnalysisId, job.status)
      if (isRunningStatus(job.status)) {
        rememberAnalysisJob(affectedAnalysisId, job.job_id)
      } else {
        forgetAnalysisJob(affectedAnalysisId)
      }
      if (isRunningStatus(job.status) && job.replace_analysis_id) reanalyzingAnalysisId.value = job.replace_analysis_id
      if (job.replace_analysis_id && job.model) reanalyzingModel.value = job.model
    }

    if (job.status === 'completed') {
      const completedAnalysisId = job.analysis_id || affectedAnalysisId || activeAnalysisId.value || ''
      setAnalysisStatus(completedAnalysisId, 'completed')
      forgetAnalysisJob(completedAnalysisId)
      reanalyzingAnalysisId.value = ''
      reanalyzingModel.value = ''
      loading.value = false
      reanalyzeLoading.value = false
      if (completedAnalysisId) {
        await loadAnalysis(completedAnalysisId, { resumePolling: false })
      }
      await loadHistory({ preferredAnalysisId: completedAnalysisId, autoSelectFirst: false })
      clearJobState()
      ElMessage.success('拆解完成！')
      return
    }

    if (job.status === 'failed') {
      loading.value = false
      setAnalysisStatus(affectedAnalysisId, 'failed')
      forgetAnalysisJob(affectedAnalysisId)
      reanalyzingAnalysisId.value = ''
      reanalyzingModel.value = ''
      reanalyzeLoading.value = false
      clearJobState()
      ElMessage.error(job.message ? `分析失败：${job.message}` : '分析失败')
      return
    }

    if (job.status === 'canceled') {
      loading.value = false
      reanalyzeLoading.value = false
      if (job.replace_analysis_id || reanalyzingAnalysisId.value) {
        restoreCanceledReanalysisState(affectedAnalysisId)
      } else {
        setAnalysisStatus(affectedAnalysisId, 'canceled')
      }
      forgetAnalysisJob(affectedAnalysisId)
      reanalyzingAnalysisId.value = ''
      reanalyzingModel.value = ''
      clearJobState()
      ElMessage.info(job.message || '已停止生成')
      return
    }

    loading.value = true
    scheduleJobPolling(jobId)
    if (manual) ElMessage.info(job.message || '后台分析中')
  } catch (err) {
    console.error('poll job failed:', err)
    if (err?.response?.status === 404) {
      loading.value = false
      reanalyzeLoading.value = false
      reanalyzingAnalysisId.value = ''
      reanalyzingModel.value = ''
      clearJobState()
      ElMessage.warning('后台任务状态不存在，可能后端重启过；已完成的结果可在历史记录中查看')
      await loadHistory({ autoSelectFirst: false })
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

const resumeAnalysisPolling = async (analysisId) => {
  if (!analysisId) return
  const knownJobId = pendingAnalysisJobs.value[analysisId]
  if (knownJobId) {
    currentJobId.value = knownJobId
    reanalyzingAnalysisId.value = analysisId
    loading.value = true
    reanalyzeLoading.value = true
    await pollJobStatus(knownJobId)
    return
  }

  try {
    const res = await axios.get(`/api/analysis-jobs/by-analysis/${analysisId}`, { timeout: 10000 })
    const job = res.data.data
    if (!job?.job_id) return

    setAnalysisStatus(analysisId, job.status)
    currentJobId.value = job.job_id
    jobStatus.value = job.status
    jobMessage.value = job.message || ''

    if (isRunningStatus(job.status)) {
      rememberAnalysisJob(analysisId, job.job_id)
      reanalyzingAnalysisId.value = analysisId
      reanalyzingModel.value = job.model || ''
      loading.value = true
      reanalyzeLoading.value = true
      await pollJobStatus(job.job_id)
      return
    }

    forgetAnalysisJob(analysisId)
    loading.value = false
    reanalyzeLoading.value = false
  } catch (err) {
    if (err?.response?.status !== 404) {
      console.error('resume analysis polling failed:', err)
    }
  }
}

const loadHistory = async (options = {}) => {
  const {
    preferredAnalysisId = '',
    autoSelectFirst = true,
  } = options
  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await axios.get('/api/analyses', { timeout: 10000 })
    const list = res.data.data || []
    historyList.value = list
    list.forEach((item) => {
      if (isPendingHistoryItem(item)) setAnalysisStatus(item.id, item.status || 'queued')
    })

    if (!list.length) return

    const preferredHistoryItem = preferredAnalysisId
      ? list.find((item) => !isPendingHistoryItem(item) && item.id === preferredAnalysisId)
      : null
    const activeStillExists = Boolean(activeAnalysisId.value)
      && list.some((item) => !isPendingHistoryItem(item) && item.id === activeAnalysisId.value)

    if (preferredHistoryItem) {
      await loadAnalysis(preferredHistoryItem.id)
      return
    }

    if (activeStillExists) return

    const firstCompleted = list.find((item) => !isPendingHistoryItem(item))
    if (autoSelectFirst && firstCompleted?.id) {
      await loadAnalysis(firstCompleted.id)
    }
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
    updateReanalyzeModelType()
  } catch (err) {
    console.error('load model options failed:', err)
    modelOptions.value = []
    modelType.value = ''
    reanalyzeModelType.value = ''
    ElMessage.error('模型配置加载失败，请确认后端服务已启动')
  }
}

const loadAnalysis = async (id, options = {}) => {
  if (!id) return
  const { resumePolling = true } = options
  const isSwitchingAnalysis = Boolean(activeAnalysisId.value && activeAnalysisId.value !== id)
  if (isSwitchingAnalysis) stopCurrentPolling()
  try {
    const res = await axios.get(`/api/analyses/${id}`, { timeout: 10000 })
    const detail = res.data.data
    applyAnalysisDetail(detail)
    if (resumePolling && isRunningStatus(getAnalysisStatus(id))) {
      await resumeAnalysisPolling(id)
    } else {
      loading.value = false
      reanalyzeLoading.value = false
    }
  } catch (err) {
    console.error('load analysis failed:', err)
    const detail = err?.response?.data?.detail || err?.message
    ElMessage.error(detail ? `记录加载失败：${detail}` : '记录加载失败')
  }
}

const handleHistorySelect = async (item) => {
  if (!item?.id) return
  if (isPendingHistoryItem(item)) {
    currentJobId.value = item.job_id || item.id
    jobStatus.value = item.status || 'queued'
    jobMessage.value = item.message || '后台分析中'
    currentFileName.value = item.filename || currentFileName.value
    activeAnalysisId.value = ''
    reanalyzingAnalysisId.value = ''
    reanalyzingModel.value = ''
    loading.value = isRunningStatus(jobStatus.value)
    localStorage.setItem('videoAnalyzePendingJobId', currentJobId.value)
    pollJobStatus(currentJobId.value, true)
    return
  }
  if (hasRunningInitialAnalysisJob()) {
    await loadHistory({ autoSelectFirst: false })
  }
  loadAnalysis(item.id)
}

const clearCurrentAnalysis = () => {
  resultList.value = []
  analysisVersions.value = []
  selectedCompareModels.value = []
  activeAnalysisId.value = ''
  currentAnalysisModel.value = ''
  reanalyzeModelType.value = ''
  reanalyzingAnalysisId.value = ''
  reanalyzingModel.value = ''
  currentFileName.value = ''
  videoUrlInput.value = ''
  currentFile = null
  fileList.value = []
  setVideoPreview('', false)
  analysisVersion.value = Date.now()
}

const confirmDeleteAnalysis = async (item) => {
  if (!item?.id) return
  const isPendingItem = isPendingHistoryItem(item)

  try {
    await ElMessageBox.confirm(
      isPendingItem
        ? `确定删除「${item.filename || '这个分析任务'}」吗？删除后会停止后端正在进行的分析任务。`
        : `确定删除「${item.filename || '这条视频拆解'}」吗？删除后该视频、分镜图片和拆解结果都会移除。`,
      isPendingItem ? '删除并停止任务' : '删除拆解记录',
      {
        confirmButtonText: isPendingItem ? '确认删除并停止' : '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  try {
    await axios.delete(`/api/analyses/${item.id}`, { timeout: 10000 })
    if (isPendingItem && (item.job_id || item.id) === currentJobId.value) {
      clearJobState()
      loading.value = false
      reanalyzeLoading.value = false
      reanalyzingAnalysisId.value = ''
      reanalyzingModel.value = ''
    }
    if (!isPendingItem && item.id === activeAnalysisId.value) {
      clearJobState()
      loading.value = false
      clearCurrentAnalysis()
    }
    await loadHistory()
    ElMessage.success(isPendingItem ? '已删除任务并停止分析' : '已删除拆解记录')
  } catch (err) {
    console.error('delete analysis failed:', err)
    const detail = err?.response?.data?.detail || err?.message
    ElMessage.error(detail ? `删除失败：${detail}` : '删除失败')
  }
}

onMounted(() => {
  Object.keys(pendingAnalysisJobs.value).forEach((analysisId) => {
    setAnalysisStatus(analysisId, 'processing')
  })
  loadModelOptions()
  const pendingJobId = localStorage.getItem('videoAnalyzePendingJobId')
  loadHistory({ autoSelectFirst: !pendingJobId })
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
  max-width: 1560px;
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

.granularity-control {
  flex: 0 0 auto;
}

.video-url-input {
  width: min(420px, 48vw);
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

.manual-transcript-panel {
  display: grid;
  gap: 10px;
  margin: 0 0 16px;
  padding: 12px 14px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #ffffff;
}

.manual-transcript-panel h3 {
  margin: 2px 0 0;
  color: #1d2939;
  font-size: 14px;
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

.history-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.product-filter {
  width: 160px;
}

.history-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  column-gap: 10px;
  row-gap: 16px;
}

.history-card {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 12px;
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

.history-cover {
  display: block;
  width: 56px;
  aspect-ratio: 9 / 16;
  overflow: hidden;
  align-self: start;
  background: #eef2f7;
  border: 1px solid #dce5ef;
  border-radius: 8px;
}

.history-cover img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.history-cover-empty {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  color: #98a2b3;
  font-size: 12px;
  font-weight: 700;
}

.history-info {
  display: grid;
  min-width: 0;
  gap: 5px;
  align-content: start;
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
  gap: 8px;
}

.history-job-message {
  min-width: 0;
  overflow: hidden;
  color: #667085;
  font-size: 12px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  margin-bottom: 18px;
}

.result-title-block {
  min-width: 0;
  width: 100%;
}

.result-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.result-title-row > div:first-child {
  min-width: 0;
  flex: 1 1 auto;
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
  flex: 0 0 auto;
  align-items: flex-end;
  gap: 8px;
  flex-direction: column;
  justify-content: flex-end;
  max-width: 220px;
}

.reanalyze-controls,
.empty-result-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.reanalyze-model-select {
  width: 138px;
}

.category-reason {
  margin: 8px 0 0;
  color: #667085;
  line-height: 1.6;
  font-size: 12px;
}

.version-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin: 0 0 16px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e5ebf3;
  border-radius: 8px;
}

.version-toolbar span {
  color: #667085;
  font-size: 13px;
  font-weight: 700;
}

.model-result-grid {
  display: grid;
  gap: 18px;
  align-items: start;
}

.compare-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.model-result-card {
  min-width: 0;
  padding: 14px;
  background: rgba(248, 250, 252, 0.78);
  border: 1px solid #dfe6f0;
  border-radius: 8px;
}

.compare-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  color: #101828;
}

.compare-head span {
  color: #667085;
  font-size: 12px;
  white-space: nowrap;
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

.story-list.compact .story-item {
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 10px;
}

.story-list.compact .shot-thumb {
  width: 48px;
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

.script-block {
  margin: 0 0 12px;
}

.script-label {
  display: block;
  margin: 0 0 4px;
  color: #667085;
  font-size: 11px;
  font-weight: 700;
}

.script-text {
  margin: 0;
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

.empty-result.is-loading {
  justify-items: center;
}

.empty-result-spinner {
  width: 28px;
  height: 28px;
  margin-bottom: 16px;
  border: 3px solid #d8e8fb;
  border-top-color: #2b7de9;
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

.empty-result.is-loading h3 {
  color: #263245;
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

  .compare-grid {
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

  .result-title-row {
    flex-direction: column;
    gap: 10px;
  }

  .result-actions {
    align-items: flex-start;
    max-width: none;
    width: 100%;
  }

  .history-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-actions {
    justify-content: flex-start;
    width: 100%;
  }
}

@media (max-width: 640px) {
  .analyze-page {
    padding: 14px;
  }

  .model-select {
    width: 100%;
  }

  .video-url-input {
    width: 100%;
  }

  .product-filter {
    width: 100%;
  }

  .tool-bar {
    width: 100%;
  }

  .reanalyze-controls,
  .empty-result-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .reanalyze-model-select {
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
.result-title {
  font-size: 16px !important;
  font-weight: 600;
  line-height: 1.4;
  margin: 0;
}
</style>
