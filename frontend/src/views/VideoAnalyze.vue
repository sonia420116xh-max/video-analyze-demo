<template>
  <div class="analyze-page">
    <section v-if="scriptCopyPageOpen" class="copy-workspace">
      <header class="copy-topbar">
        <div>
          <p class="eyebrow">一键复制脚本</p>
          <h2>{{ scriptCopySourceTitle }}</h2>
        </div>
        <div class="copy-topbar-actions">
          <el-button @click="backToAnalysisDetail">返回详情</el-button>
          <el-button
            type="primary"
            :loading="scriptCopyLoading"
            :disabled="!canSubmitScriptCopy"
            @click="generateScriptCopy"
          >
            生成新脚本
          </el-button>
        </div>
      </header>

      <div class="copy-page-grid">
        <aside class="copy-source-panel">
          <div class="copy-source-head">
            <div>
              <p class="eyebrow">源视频结构</p>
              <h3>{{ getVersionFormulaName(scriptCopySourceVersion) }}</h3>
            </div>
            <el-button
              size="small"
              plain
              :disabled="exportingScriptXlsx || !(scriptCopySourceVersion?.data || []).length"
              @click="exportSourceScriptXlsx"
            >
              导出脚本
            </el-button>
          </div>
          <div class="copy-source-tags">
            <el-tag size="small" type="success">{{ getVersionFormulaSubtype(scriptCopySourceVersion) }}</el-tag>
            <el-tag v-if="getVersionSellingPoint(scriptCopySourceVersion)" size="small" type="warning" effect="plain">
              {{ getVersionSellingPoint(scriptCopySourceVersion) }}
            </el-tag>
            <el-tag v-if="getVersionGolden3s(scriptCopySourceVersion)" size="small" type="danger" effect="plain">
              黄金3秒 {{ getVersionGolden3s(scriptCopySourceVersion) }}
            </el-tag>
          </div>
          <p class="category-reason" v-if="getVersionCategoryReason(scriptCopySourceVersion)">
            {{ getVersionCategoryReason(scriptCopySourceVersion) }}
          </p>
          <div class="copy-hook-box">
            <strong>黄金3秒复刻</strong>
            <p>{{ getGolden3sRecreationText(scriptCopySourceVersion) }}</p>
          </div>
          <div class="copy-template-list">
            <article
              v-for="(item, idx) in scriptCopySourceVersion?.data || []"
              :key="`copy-template-${idx}-${item.start_time}`"
              class="copy-template-item"
            >
              <span>{{ formatTime(item.start_time) }} - {{ formatTime(item.end_time) }}</span>
              <strong>{{ item.title || item.content_tag || `分镜 ${idx + 1}` }}</strong>
              <dl>
                <div>
                  <dt>画面/转化</dt>
                  <dd>{{ item.conversion_point || item.scene_description || '暂无画面描述' }}</dd>
                </div>
                <div>
                  <dt>口播/字幕</dt>
                  <dd>{{ formatShotScript(item) }}</dd>
                </div>
              </dl>
            </article>
          </div>
        </aside>

        <main class="copy-main-panel">
          <section class="copy-form-panel">
            <div class="copy-form-head">
              <div>
                <p class="eyebrow">用户产品</p>
                <h3>填写新脚本要带货的商品</h3>
              </div>
            </div>

            <el-form-item class="required-form-item" label="需要带货的商品">
              <div class="product-picker">
                <el-input
                  v-model="scriptCopyForm.product_name"
                  placeholder="输入商品名称，例如：Perfume Rebelle Feminino Hinode 75ml"
                  @blur="handleProductTitleBlur"
                />
                <el-upload
                  :auto-upload="false"
                  :on-change="handleScriptCopyImageChange"
                  :on-remove="handleScriptCopyImageRemove"
                  :file-list="scriptCopyImageList"
                  accept="image/*"
                  multiple
                  :show-file-list="false"
                >
                  <el-button plain>上传图片</el-button>
                </el-upload>
              </div>
            </el-form-item>

            <el-form-item label="希望突出的内容">
              <div
                class="highlight-input-wrap"
                :class="{ 'is-generating': sellingPointsGenerating }"
              >
                <el-input
                  v-model="scriptCopyForm.selling_points"
                  type="textarea"
                  :maxlength="200"
                  :rows="6"
                  resize="vertical"
                  show-word-limit
                  :placeholder="sellingPointsGenerating ? '正在根据商品信息生成卖点...' : '例如：香水, 女士, 75ml。也可以写想强调的质感、功效、价格、适用人群。'"
                  @input="handleSellingPointsInput"
                />
                <div
                  v-if="sellingPointsGenerating"
                  class="selling-points-status"
                  role="status"
                  aria-live="polite"
                >
                  <span class="selling-points-spinner" aria-hidden="true" />
                  <div>
                    <strong>AI 正在生成商品卖点</strong>
                    <p>会结合商品标题、品类和已上传图片，生成后自动填入，可继续编辑。</p>
                  </div>
                </div>
                <div v-else class="data-support-tip">
                  卖点由 AI 根据商品信息生成，用户可继续修改
                </div>
              </div>
            </el-form-item>

            <div
              class="selling-point-recommendations"
              :class="{ 'is-generating': sellingPointsGenerating }"
            >
              <strong>卖点推荐</strong>
              <div v-if="sellingPointsGenerating" class="recommend-skeleton-list" aria-hidden="true">
                <span
                  v-for="item in 6"
                  :key="`selling-point-skeleton-${item}`"
                  class="recommend-skeleton"
                />
              </div>
              <div v-else>
                <el-tag
                  v-for="tag in sellingPointRecommendationTags"
                  :key="tag"
                  class="recommend-tag"
                  round
                  effect="plain"
                  @click="appendSellingPointTag(tag)"
                >
                  {{ tag }}
                </el-tag>
              </div>
            </div>

            <el-collapse class="advanced-copy-settings">
              <el-collapse-item title="高级设置（可选）" name="advanced">
                <div class="copy-form-grid">
                  <el-form-item label="产品品类">
                    <el-input
                      v-model="scriptCopyForm.product_category"
                      placeholder="例如：香水 / 运动恢复工具"
                      @blur="generateDefaultSellingPoints"
                    />
                  </el-form-item>
                  <el-form-item label="目标用户">
                    <el-input v-model="scriptCopyForm.target_audience" placeholder="例如：女士、通勤人群、健身人群" />
                  </el-form-item>
                  <el-form-item label="使用场景">
                    <el-input v-model="scriptCopyForm.usage_scene" placeholder="例如：约会、办公室、健身后放松" />
                  </el-form-item>
                  <el-form-item label="价格/优惠">
                    <el-input v-model="scriptCopyForm.price_offer" placeholder="例如：限时 20% off、买一送一" />
                  </el-form-item>
                  <el-form-item label="目标时长">
                    <el-input v-model="scriptCopyForm.duration_seconds" placeholder="例如：18 秒" />
                  </el-form-item>
                  <el-form-item label="生成模型">
                    <el-select
                      v-model="scriptCopyForm.model"
                      class="copy-model-select"
                      placeholder="生成模型"
                      :disabled="modelOptions.length === 0"
                    >
                      <el-option
                        v-for="option in modelOptions"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item label="表达语气">
                  <el-input
                    v-model="scriptCopyForm.brand_tone"
                    placeholder="例如：真实测评、少夸张、偏口语、适合 TikTok Shop"
                  />
                </el-form-item>
                <el-form-item label="补充要求">
                  <el-input
                    v-model="scriptCopyForm.extra_requirements"
                    type="textarea"
                    :rows="3"
                    resize="vertical"
                    placeholder="可选：禁用词、必须出现的卖点、平台、语言、拍摄限制等。"
                  />
                </el-form-item>
              </el-collapse-item>
            </el-collapse>

            <div v-if="scriptCopyImageList.length" class="copy-upload-row">
              <div>
                <strong>已上传图片</strong>
                <p>模型会只依据图片中能看见的信息补充画面，不会保存到历史记录。</p>
              </div>
              <el-upload
                :auto-upload="false"
                :on-change="handleScriptCopyImageChange"
                :on-remove="handleScriptCopyImageRemove"
                :file-list="scriptCopyImageList"
                accept="image/*"
                multiple
                list-type="picture-card"
              >
                <span>继续上传</span>
              </el-upload>
            </div>
          </section>

          <section class="copy-result-panel">
            <div class="copy-result-head">
              <div>
                <p class="eyebrow">生成结果</p>
                <h3>新产品脚本</h3>
              </div>
              <el-button
                v-if="scriptCopyResult"
                size="small"
                plain
                @click="copyGeneratedScript"
              >
                复制结果
              </el-button>
              <el-button
                v-if="scriptCopyResult"
                size="small"
                type="primary"
                plain
                :loading="exportingScriptXlsx"
                @click="exportGeneratedScriptXlsx"
              >
                导出脚本
              </el-button>
            </div>

            <div v-if="scriptCopyLoading" class="copy-loading">
              <span class="empty-result-spinner" aria-hidden="true" />
              <p>正在套用源视频脚本逻辑生成新脚本...</p>
            </div>

            <div v-else-if="scriptCopyResult" class="copy-result-content">
              <div class="copy-strategy">
                <strong>复刻策略</strong>
                <p>{{ scriptCopyResult.copy_strategy?.script_logic || '已按源视频结构生成新脚本。' }}</p>
                <p>{{ scriptCopyResult.copy_strategy?.golden_3s_recreation }}</p>
              </div>

              <div class="copy-section-title">
                <strong>可拍摄分镜脚本</strong>
                <span>按源视频段落结构生成，包含画面、口播、字幕和拍摄要点。</span>
              </div>

              <article
                v-for="(shot, idx) in scriptCopyResult.shots || []"
                :key="`copy-shot-${idx}`"
                class="copy-shot-card"
              >
                <div class="copy-shot-head">
                  <span>分镜 {{ shot.shot_index || idx + 1 }}</span>
                  <strong>{{ shot.title || '脚本段落' }}</strong>
                  <em>{{ shot.duration_seconds ? `${shot.duration_seconds}s` : '' }}</em>
                </div>
                <p v-if="shot.hook_implementation" class="copy-hook-line">
                  {{ shot.hook_implementation }}
                </p>
                <dl>
                  <div v-if="shot.visual_plan">
                    <dt>画面</dt>
                    <dd>{{ shot.visual_plan }}</dd>
                  </div>
                  <div v-if="shot.voiceover">
                    <dt>口播</dt>
                    <dd>{{ shot.voiceover }}</dd>
                  </div>
                  <div v-if="shot.screen_text">
                    <dt>字幕</dt>
                    <dd>{{ shot.screen_text }}</dd>
                  </div>
                  <div v-if="shot.new_script">
                    <dt>完整脚本</dt>
                    <dd>{{ shot.new_script }}</dd>
                  </div>
                  <div v-if="shot.shooting_notes">
                    <dt>拍摄要点</dt>
                    <dd>{{ shot.shooting_notes }}</dd>
                  </div>
                  <div v-if="shot.conversion_point">
                    <dt>转化作用</dt>
                    <dd>{{ shot.conversion_point }}</dd>
                  </div>
                </dl>
              </article>

              <div v-if="!(scriptCopyResult.shots || []).length" class="copy-empty-shots">
                本次结果没有返回分镜，请重新生成或补充商品卖点后再试。
              </div>

              <div v-if="scriptCopyResult.cta_options?.length" class="copy-cta-box">
                <strong>结尾 CTA 备选</strong>
                <p>{{ scriptCopyResult.cta_options.join(' / ') }}</p>
              </div>
            </div>

            <div v-else class="copy-empty-result">
              填写产品信息后生成脚本。系统会复用源视频的爆款结构、分镜节奏、卖点角度和黄金3秒钩子实现方式。
            </div>
          </section>
        </main>
      </div>
    </section>

    <section v-else class="workspace">
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
                            size="small"
                            type="success"
                            plain
                            :disabled="!activeAnalysisId"
                            @click="openScriptCopyPage(version)"
                          >
                            一键复制
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
                      <el-popover
                        v-if="getVersionGolden3s(version)"
                        placement="bottom-start"
                        trigger="click"
                        width="360"
                      >
                        <template #reference>
                          <el-tag class="clickable-tag" size="small" type="danger" effect="plain">
                            黄金3秒 {{ getVersionGolden3s(version) }}
                          </el-tag>
                        </template>
                        <div class="hook-popover">
                          <strong>怎么命中</strong>
                          <p>{{ getVersionGolden3sReason(version) }}</p>
                          <strong>怎么复刻</strong>
                          <p>{{ getGolden3sRecreationText(version) }}</p>
                        </div>
                      </el-popover>
                      <!-- <el-tag v-if="version.model" size="small" type="info" effect="plain">
                        {{ version.model }}
                      </el-tag> -->
                    </div>
                    <p class="category-reason" v-if="getVersionCategoryReason(version)">
                      {{ getVersionCategoryReason(version) }}
                    </p>
                    <div v-if="getVersionViralSummary(version)" class="viral-summary-box">
                      <strong>爆点解析</strong>
                      <p>{{ getVersionViralSummary(version) }}</p>
                    </div>
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
                        <blockquote class="script-text" v-html="formatHighlightedShotScript(item)"></blockquote>
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
const scriptCopyPageOpen = ref(false)
const scriptCopyLoading = ref(false)
const scriptCopyResult = ref(null)
const scriptCopySourceModel = ref('')
const scriptCopyImageList = ref([])
const scriptCopyImageFiles = ref([])
const scriptCopyImagePreviewUrls = ref({})
const scriptCopySellingPointsTouched = ref(false)
const sellingPointsGenerating = ref(false)
const exportingScriptXlsx = ref(false)
const sellingPointsRequestSeq = ref(0)
const lastSellingPointsProductTitle = ref('')
const sellingPointRecommendationTags = [
  '物流快',
  '客服服务态度好',
  '产品质量好',
  '适用人群',
  '价格划算',
  '送礼合适',
  '香味持久',
  '包装精致',
]
const createEmptyScriptCopyForm = () => ({
  model: '',
  product_name: '',
  product_category: '',
  target_audience: '',
  selling_points: '',
  usage_scene: '',
  price_offer: '',
  brand_tone: '',
  duration_seconds: '',
  extra_requirements: '',
})
const scriptCopyForm = ref(createEmptyScriptCopyForm())

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

const PRODUCT_CLASSIFICATION_RULES = [
  {
    classification: '美妆个护',
    keywords: ['香水', 'perfume', 'fragrance', '口红', '精华', '面霜', '护肤', '美妆', '洗发', '护发', 'serum', 'cream', 'makeup'],
    sellingPoints: ['香味有记忆点', '适合日常通勤', '送礼合适', '包装精致'],
  },
  {
    classification: '手机与数码',
    keywords: ['手机', '耳机', '充电', '数据线', '手机壳', 'phone', 'earbuds', 'charger', 'case'],
    sellingPoints: ['使用方便', '兼容性好', '外观质感好', '日常高频使用'],
  },
  {
    classification: '运动与户外',
    keywords: ['健身', '瑜伽', '筋膜枪', '运动', '户外', '露营', 'fitness', 'massage gun', 'sport', 'outdoor'],
    sellingPoints: ['便携好用', '适合运动后放松', '上手门槛低', '省时间'],
  },
  {
    classification: '家居用品',
    keywords: ['收纳', '清洁', '浴室', '家居', '拖把', 'storage', 'cleaning', 'bathroom', 'home'],
    sellingPoints: ['解决日常痛点', '操作省力', '让空间更整洁', '适合家庭使用'],
  },
  {
    classification: '厨房用品',
    keywords: ['厨房', '锅', '餐具', '杯', 'kitchen', 'cookware', 'cup', 'bottle'],
    sellingPoints: ['使用方便', '清洁省心', '适合日常做饭', '质感耐用'],
  },
  {
    classification: '女装与女士内衣',
    keywords: ['女装', '连衣裙', '裙', '内衣', 'dress', 'women', 'feminina', 'blusa', 'camisa', 'lingerie', 'skirt'],
    sellingPoints: ['上身效果好', '版型显身材', '面料舒适', '适合多场景穿搭'],
  },
  {
    classification: '男装与男士内衣',
    keywords: ['男装', '男士', '衬衫', '裤', 'menswear', 'shirt', 'pants'],
    sellingPoints: ['版型利落', '日常百搭', '面料舒适', '适合通勤'],
  },
  {
    classification: '鞋靴',
    keywords: ['鞋', '靴', '运动鞋', '凉鞋', 'shoe', 'sneaker', 'boots', 'sandals'],
    sellingPoints: ['脚感舒适', '好搭配', '适合长时间穿', '款式耐看'],
  },
  {
    classification: '食品饮料',
    keywords: ['食品', '零食', '饮料', '咖啡', '茶', 'food', 'snack', 'coffee', 'tea', 'drink'],
    sellingPoints: ['口味有记忆点', '适合囤货', '方便即食', '性价比高'],
  },
  {
    classification: '保健',
    keywords: ['保健', '营养', '维生素', '补剂', '镁', 'magnesium', 'supplement', 'vitamin', 'health', 'wellness', 'mineral'],
    sellingPoints: ['成分信息明确', '日常补充方便', '适合关注健康管理人群', '规格清晰'],
  },
  {
    classification: '玩具和爱好',
    keywords: ['玩具', '手工', '编织', '毛线', '钩针', 'amigurumi', 'linha', 'balloon', 'yarn', 'crochet', 'knitting'],
    sellingPoints: ['适合手工创作', '用途明确', '规格清晰', '适合玩偶编织'],
  },
  {
    classification: '宠物用品',
    keywords: ['宠物', '猫', '狗', '猫砂', 'pet', 'cat', 'dog'],
    sellingPoints: ['宠物家庭适用', '省心省力', '清洁方便', '提升日常照护效率'],
  },
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
const scriptCopySourceVersion = computed(() => {
  if (scriptCopySourceModel.value) return getVersionByModel(scriptCopySourceModel.value) || activeVersion.value || fallbackDisplayVersion.value
  return activeVersion.value || fallbackDisplayVersion.value
})
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
const scriptCopySourceTitle = computed(() => {
  const formula = getVersionFormulaName(scriptCopySourceVersion.value)
  const subtype = getVersionFormulaSubtype(scriptCopySourceVersion.value)
  return `${currentFileName.value || '当前视频'} · ${formula} / ${subtype}`
})
const canSubmitScriptCopy = computed(() => (
  Boolean(activeAnalysisId.value)
  && Boolean(scriptCopyForm.value.model)
  && (
    Boolean(scriptCopyForm.value.product_name.trim())
    || Boolean(scriptCopyForm.value.selling_points.trim())
    || scriptCopyImageFiles.value.length > 0
  )
))

const isModelAvailable = (value) => modelOptions.value.some((option) => option.value === value)
const preferredScriptCopyModel = () => {
  if (isModelAvailable('gpt-4o')) return 'gpt-4o'
  return modelOptions.value[0]?.value || ''
}
const preferredSellingPointsModel = () => preferredScriptCopyModel() || 'gpt-4o'
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

const getVersionProductClassification = (version) => (
  version?.product_classification
  || getVersionFirstItem(version)?.product_classification
  || ''
)

const getVersionSellingPoint = (version) => formatSellingPoint(getVersionFirstItem(version))

const getVersionGolden3s = (version) => formatGolden3s(getVersionFirstItem(version))

const getVersionGolden3sReason = (version) => (
  getVersionFirstItem(version)?.golden_3s_reason
  || '开头 0-3 秒通过具体问题、悬念、数据、技巧或争议制造继续观看理由。'
)

const getVersionOpeningHookSummary = (version) => (
  getVersionFirstItem(version)?.opening_hook_summary
  || getVersionFirstItem(version)?.golden_3s_reason
  || ''
)

const getVersionOpeningHookEvidence = (version) => (
  getVersionFirstItem(version)?.opening_hook_evidence
  || getVersionFirstItem(version)?.script
  || ''
)

const getVersionViralSummary = (version) => (
  getVersionFirstItem(version)?.viral_reason_summary
  || ''
)

const getGolden3sRecreationText = (version) => {
  const item = getVersionFirstItem(version)
  const hook = item?.golden_3s_hook || ''
  const subtype = item?.golden_3s_subtype || ''
  if (!hook && !subtype) {
    return getVersionOpeningHookSummary(version) || '这条视频没有命中固定黄金3秒分类，但仍要复刻第一分镜的留人机制，用首个画面快速制造继续观看理由。'
  }
  const subtypeRules = {
    省钱秘笈: '先抛出低价发现、隐藏福利或购买路径，再马上用产品画面证明划算不是空话。',
    比价追问: '开头提出“哪一个更值得买”的选择题，再用后续分镜逐步给出判断理由。',
    痛点提问: '先问目标用户正在经历的具体麻烦，再让产品进入同一个问题现场。',
    好奇提问: '先留下一个信息缺口，再用产品细节或使用过程补上答案。',
    成本提问: '先追问真实花费或浪费成本，再把新产品的价值换算成更容易判断的数字。',
    槽点揭露: '先指出旧方法或热门选择的具体缺陷，再让新产品承担解决方案。',
    价格挑衅: '用便宜选择挑战昂贵选择，再用效果、质感或规格证明它值得买。',
    悬念验证: '先设置“到底有没有用”的测试悬念，把结论留到后面兑现。',
    结果前置: '先展示最有冲击力的结果、数字或变化，再解释产品如何做到。',
  }
  const hookRules = {
    提问式: '把开场写成目标用户能立刻代入的具体问题。',
    挑战式: '设置一个可验证的测试或挑战，后续分镜必须兑现。',
    '秘诀/技巧': '承诺一个具体技巧、避坑经验或购买路径，后续要交付方法。',
    震撼数据: '用具体数字、时间、比例或价格差开场，并在后续解释来源。',
    争议式: '用明确立场或冲突对象开场，但要落回产品真实卖点。',
  }
  return subtypeRules[subtype] || hookRules[hook] || '复刻开头的信息差、悬念或冲突结构，但替换为用户产品真实可证明的卖点。'
}

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

const escapeHtml = (value) => String(value || '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const formatHighlightedShotScript = (item) => {
  const script = formatShotScript(item)
  const evidence = String(item?.opening_hook_evidence || item?.golden_3s_reason || '').trim()
  if (!evidence || script === '该段无有效口播/字幕') return escapeHtml(script)
  const candidates = [
    evidence,
    ...evidence.split(/[。.!！？?\n]/),
  ].map((text) => text.trim()).filter((text) => text.length >= 4)

  let highlighted = escapeHtml(script)
  for (const candidate of candidates) {
    const escapedCandidate = escapeHtml(candidate)
    if (!escapedCandidate || !highlighted.includes(escapedCandidate)) continue
    highlighted = highlighted.replace(
      escapedCandidate,
      `<mark class="golden-script-highlight">${escapedCandidate}</mark>`,
    )
    return highlighted
  }
  return highlighted
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

const openScriptCopyPage = (version) => {
  if (!activeAnalysisId.value) {
    ElMessage.warning('请先选择一条已完成的视频拆解')
    return
  }
  scriptCopySourceModel.value = version?.model || currentAnalysisModel.value || ''
  revokeScriptCopyImagePreviews()
  scriptCopyForm.value = {
    ...createEmptyScriptCopyForm(),
    model: preferredScriptCopyModel(),
    duration_seconds: estimateSourceDurationSeconds(version),
  }
  scriptCopyResult.value = null
  scriptCopyImageList.value = []
  scriptCopyImageFiles.value = []
  scriptCopySellingPointsTouched.value = false
  sellingPointsGenerating.value = false
  sellingPointsRequestSeq.value += 1
  lastSellingPointsProductTitle.value = ''
  scriptCopyPageOpen.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const backToAnalysisDetail = () => {
  scriptCopyPageOpen.value = false
}

const estimateSourceDurationSeconds = (version) => {
  const items = version?.data || []
  const lastEnd = Math.max(0, ...items.map((item) => toSeconds(item.end_time)))
  return lastEnd ? String(Math.round(lastEnd)) : ''
}

const sanitizeFileName = (name) => String(name || 'script')
  .replace(/[\\/:*?"<>|]+/g, '-')
  .replace(/\s+/g, ' ')
  .trim()
  .slice(0, 80) || 'script'

const formatExportTimeRange = (start, end) => `${formatTime(start)}~${formatTime(end)}`

const getShotScriptText = (item) => (
  item.script
  || item.subtitle
  || item.transcript
  || item.voiceover
  || formatShotScript(item)
  || ''
)

const getShotScriptTranslation = (item) => (
  item.script_translation
  || item.translation
  || item.subtitle_translation
  || item.script_cn
  || ''
)

const formatGeneratedScriptText = (shot) => [
  shot.voiceover ? `口播：${shot.voiceover}` : '',
  shot.screen_text ? `字幕：${shot.screen_text}` : '',
].filter(Boolean).join('\n') || shot.new_script || ''

const buildSourceScriptExportRows = () => (scriptCopySourceVersion.value?.data || []).map((item, index) => ({
  sequence: index + 1,
  structure: item.title || item.content_tag || item.narrative_role || `分镜 ${index + 1}`,
  timeRange: formatExportTimeRange(item.start_time, item.end_time),
  imageUrl: item.image_url ? getImageUrl(item.image_url) : '',
  scriptText: getShotScriptText(item),
  scriptTranslation: [
    getShotScriptTranslation(item),
    index === 0 && item.opening_hook_evidence ? `黄金3秒证据：${item.opening_hook_evidence}` : '',
  ].filter(Boolean).join('\n'),
  description: [
    item.scene_description || '',
    item.conversion_point ? `转化作用：${item.conversion_point}` : '',
    index === 0 && item.opening_hook_summary ? `开头爆点：${item.opening_hook_summary}` : '',
    index === 0 && item.viral_reason_summary ? `爆款解析：${item.viral_reason_summary}` : '',
    item.visual_tactic ? `拍摄手法：${item.visual_tactic}` : '',
  ].filter(Boolean).join('\n'),
}))

const buildGeneratedScriptExportRows = () => (scriptCopyResult.value?.shots || []).map((shot, index) => ({
  sequence: shot.shot_index || index + 1,
  structure: shot.title || `分镜 ${index + 1}`,
  timeRange: shot.duration_seconds ? `${shot.duration_seconds}s` : '',
  imageUrl: '',
  scriptText: formatGeneratedScriptText(shot),
  scriptTranslation: '',
  description: [
    shot.visual_plan ? `画面：${shot.visual_plan}` : '',
    shot.new_script ? `完整脚本：${shot.new_script}` : '',
    shot.shooting_notes ? `拍摄要点：${shot.shooting_notes}` : '',
    shot.conversion_point ? `转化作用：${shot.conversion_point}` : '',
    shot.hook_implementation ? `黄金3秒：${shot.hook_implementation}` : '',
  ].filter(Boolean).join('\n'),
}))

const getImageExtension = (contentType, url = '') => {
  if (contentType.includes('png') || /\.png($|\?)/i.test(url)) return 'png'
  if (contentType.includes('gif') || /\.gif($|\?)/i.test(url)) return 'gif'
  return 'jpeg'
}

const fetchImageForWorkbook = async (url) => {
  if (!url) return null
  try {
    const res = await fetch(url)
    if (!res.ok) return null
    const blob = await res.blob()
    return {
      buffer: await blob.arrayBuffer(),
      extension: getImageExtension(blob.type || '', url),
    }
  } catch (err) {
    console.warn('fetch export image failed:', err)
    return null
  }
}

const exportScriptRowsToXlsx = async ({ rows, fileName, title }) => {
  if (!rows.length) {
    ElMessage.warning('暂无可导出的脚本')
    return
  }
  exportingScriptXlsx.value = true
  try {
    const ExcelJS = await import('exceljs')
    const workbook = new ExcelJS.Workbook()
    const sheet = workbook.addWorksheet('Sheet1', {
      views: [{ state: 'frozen', ySplit: 2 }],
      properties: { defaultRowHeight: 22 },
    })
    sheet.mergeCells('A1:G1')
    sheet.getCell('A1').value = title || '脚本导出'
    sheet.getCell('A1').alignment = { horizontal: 'center', vertical: 'middle' }
    sheet.getCell('A1').font = { bold: true, size: 16, color: { argb: 'FF8000A8' } }
    sheet.getRow(1).height = 34

    sheet.getRow(2).values = ['分镜序号', '脚本结构', '分镜时间轴', '分镜首帧', '脚本文案', '脚本文案翻译', '分镜描述']
    sheet.getRow(2).height = 28
    sheet.getRow(2).eachCell((cell) => {
      cell.font = { bold: true, size: 12, color: { argb: 'FF000000' } }
      cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF8FAFC' } }
      cell.border = {
        top: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        left: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        right: { style: 'thin', color: { argb: 'FFE5E7EB' } },
      }
    })

    sheet.columns = [
      { key: 'sequence', width: 10 },
      { key: 'structure', width: 18 },
      { key: 'timeRange', width: 18 },
      { key: 'image', width: 18 },
      { key: 'scriptText', width: 42 },
      { key: 'scriptTranslation', width: 42 },
      { key: 'description', width: 48 },
    ]

    for (const [index, row] of rows.entries()) {
      const excelRow = sheet.getRow(index + 3)
      excelRow.values = [
        row.sequence,
        row.structure,
        row.timeRange,
        '',
        row.scriptText,
        row.scriptTranslation,
        row.description,
      ]
      excelRow.height = row.imageUrl ? 92 : 72
      excelRow.eachCell((cell) => {
        cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
        cell.border = {
          top: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          left: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          bottom: { style: 'thin', color: { argb: 'FFE5E7EB' } },
          right: { style: 'thin', color: { argb: 'FFE5E7EB' } },
        }
      })
      ;[5, 6, 7].forEach((col) => {
        excelRow.getCell(col).alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      })
      const image = await fetchImageForWorkbook(row.imageUrl)
      if (image) {
        const imageId = workbook.addImage({ buffer: image.buffer, extension: image.extension })
        sheet.addImage(imageId, {
          tl: { col: 3.28, row: index + 2.18 },
          ext: { width: 88, height: 88 },
          editAs: 'oneCell',
        })
      }
    }

    const buffer = await workbook.xlsx.writeBuffer()
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${sanitizeFileName(fileName)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('脚本已导出')
  } catch (err) {
    console.error('export script xlsx failed:', err)
    ElMessage.error('导出脚本失败')
  } finally {
    exportingScriptXlsx.value = false
  }
}

const exportSourceScriptXlsx = () => exportScriptRowsToXlsx({
  rows: buildSourceScriptExportRows(),
  title: '原视频脚本导出',
  fileName: `${currentFileName.value || 'source-video'}-原视频脚本`,
})

const exportGeneratedScriptXlsx = () => exportScriptRowsToXlsx({
  rows: buildGeneratedScriptExportRows(),
  title: '新脚本导出',
  fileName: `${scriptCopyForm.value.product_name || currentFileName.value || 'generated'}-新脚本`,
})

const getUploadFileKey = (file) => String(file?.uid || file?.name || file?.raw?.name || '')

const revokeScriptCopyImagePreviews = (keepKeys = new Set()) => {
  const nextUrls = {}
  Object.entries(scriptCopyImagePreviewUrls.value).forEach(([key, url]) => {
    if (keepKeys.has(key)) {
      nextUrls[key] = url
      return
    }
    URL.revokeObjectURL(url)
  })
  scriptCopyImagePreviewUrls.value = nextUrls
}

const normalizeScriptCopyUploadFiles = (uploadFiles) => {
  const keepKeys = new Set()
  const normalizedFiles = uploadFiles.map((file) => {
    const key = getUploadFileKey(file)
    if (!key) return file
    keepKeys.add(key)
    if (!file.url && file.raw) {
      const existingUrl = scriptCopyImagePreviewUrls.value[key]
      const previewUrl = existingUrl || URL.createObjectURL(file.raw)
      scriptCopyImagePreviewUrls.value = {
        ...scriptCopyImagePreviewUrls.value,
        [key]: previewUrl,
      }
      return {
        ...file,
        url: previewUrl,
      }
    }
    return file
  })
  revokeScriptCopyImagePreviews(keepKeys)
  scriptCopyImageList.value = normalizedFiles
  scriptCopyImageFiles.value = normalizedFiles.map((file) => file.raw).filter(Boolean)
  generateDefaultSellingPoints()
}

const handleScriptCopyImageChange = (_file, uploadFiles) => {
  normalizeScriptCopyUploadFiles(uploadFiles)
}

const handleScriptCopyImageRemove = (_file, uploadFiles) => {
  normalizeScriptCopyUploadFiles(uploadFiles)
}

const scriptCopyProductText = () => [
  scriptCopyForm.value.product_name,
  scriptCopyForm.value.product_category,
  scriptCopyForm.value.selling_points,
  ...scriptCopyImageList.value.map((file) => file.name || file.raw?.name || ''),
].join(' ').toLowerCase()

const inferScriptCopyProductClassification = () => {
  const text = scriptCopyProductText()
  if (!text.trim()) return ''
  const matchedRule = PRODUCT_CLASSIFICATION_RULES.find((rule) => (
    rule.keywords.some((keyword) => text.includes(keyword.toLowerCase()))
  ))
  return matchedRule?.classification || ''
}

const getScriptCopyProductSourceText = () => [
  scriptCopyForm.value.product_name,
  scriptCopyForm.value.product_category,
  ...scriptCopyImageList.value.map((file) => file.name || file.raw?.name || ''),
].join(' ')

const extractAttributeSellingPoints = (sourceText) => {
  const text = sourceText.toLowerCase()
  const points = []
  const addPoint = (condition, point) => {
    if (condition && !points.includes(point)) points.push(point)
  }

  addPoint(/\b(blusa|camisa)\b/.test(text), '女士上衣')
  addPoint(/\bplus size\b|大码|大尺码/.test(text), '大码')
  addPoint(/\bfeminina\b|women|ladies|女士|女式/.test(text), '女士')
  addPoint(/\bsocial\b|社交|通勤|office/.test(text), '社交场合')
  addPoint(/\bviscolinho\b|viscose|粘胶/.test(text), '粘胶纤维')
  addPoint(/\bamigurumi\b|玩偶编织|钩织玩偶/.test(text), '玩偶编织')
  addPoint(/\blinha\b|yarn|毛线|编织线/.test(text), '编织线')
  addPoint(/\bballoon\b|气球线/.test(text), '气球线')
  addPoint(/\bmagnesium\b|镁/.test(text), '镁元素补充')
  addPoint(/\bcomplex\b|复合/.test(text), '复合配方')
  addPoint(/\bsupplement\b|补剂|营养/.test(text), '营养补剂')
  addPoint(/\bessential\b|基础/.test(text), '基础日常补充')

  const sizeRangeMatch = sourceText.match(/\b(\d{2})\s*(?:ao|a|to|-)\s*(\d{2})\b/i)
  if (sizeRangeMatch) addPoint(true, `${sizeRangeMatch[1]}到${sizeRangeMatch[2]}`)

  const specMatches = [...sourceText.matchAll(/\b\d+(?:[.,]\d+)?\s?(?:ml|g|mg|oz|pcs|pack|capsules?)\b/gi)]
  specMatches.forEach((match) => addPoint(true, match[0].replace(/\s+/g, '')))

  return points
}

const getInferredSellingPoints = () => {
  const text = scriptCopyProductText()
  const matchedRule = PRODUCT_CLASSIFICATION_RULES.find((rule) => (
    rule.keywords.some((keyword) => text.includes(keyword.toLowerCase()))
  ))
  const attributePoints = extractAttributeSellingPoints(getScriptCopyProductSourceText())
  const fallbackPoints = matchedRule?.sellingPoints || ['品类明确', '适用人群明确', '使用场景清晰']
  const points = attributePoints.length >= 2
    ? attributePoints
    : [...attributePoints, ...fallbackPoints]
  return [...new Set(points)].slice(0, 6)
}

const getNormalizedProductTitle = () => scriptCopyForm.value.product_name.trim()

const applyDefaultSellingPoints = ({ force = false } = {}) => {
  if (!force && scriptCopySellingPointsTouched.value) return
  if (!force && scriptCopyForm.value.selling_points.trim()) return
  const points = getInferredSellingPoints()
  if (!points.length) return
  scriptCopyForm.value.selling_points = points.join('、').slice(0, 200)
}

const hasScriptCopyProductInput = () => (
  Boolean(scriptCopyForm.value.product_name.trim())
  || Boolean(scriptCopyForm.value.product_category.trim())
  || scriptCopyImageFiles.value.length > 0
)

const buildSellingPointsFormData = () => {
  const fd = new FormData()
  fd.append('model', scriptCopyForm.value.model || preferredSellingPointsModel())
  const fields = [
    'product_name',
    'product_category',
    'target_audience',
    'usage_scene',
    'price_offer',
    'extra_requirements',
  ]
  fields.forEach((key) => {
    const value = String(scriptCopyForm.value[key] || '').trim()
    if (value) fd.append(key, value)
  })
  const currentSellingPoints = scriptCopyForm.value.selling_points.trim()
  if (currentSellingPoints) fd.append('current_selling_points', currentSellingPoints)
  scriptCopyImageFiles.value.forEach((file) => fd.append('product_images', file))
  return fd
}

const generateDefaultSellingPoints = async ({ force = false } = {}) => {
  if (!force && scriptCopySellingPointsTouched.value) return
  if (!force && scriptCopyForm.value.selling_points.trim()) return
  if (!hasScriptCopyProductInput()) return

  const requestSeq = sellingPointsRequestSeq.value + 1
  sellingPointsRequestSeq.value = requestSeq
  sellingPointsGenerating.value = true
  const requestedTitle = getNormalizedProductTitle()
  if (force && requestedTitle !== lastSellingPointsProductTitle.value) {
    scriptCopySellingPointsTouched.value = false
    scriptCopyForm.value.selling_points = ''
  }
  try {
    const res = await axios.post('/api/product-selling-points', buildSellingPointsFormData(), { timeout: 120000 })
    if (requestSeq !== sellingPointsRequestSeq.value || (!force && scriptCopySellingPointsTouched.value)) return
    const points = res.data.data?.selling_points || []
    if (points.length) {
      scriptCopyForm.value.selling_points = points.join('、').slice(0, 200)
      lastSellingPointsProductTitle.value = requestedTitle
      if (force) scriptCopySellingPointsTouched.value = false
      if (res.data.data?.product_classification && !scriptCopyForm.value.product_category.trim()) {
        scriptCopyForm.value.product_category = res.data.data.product_classification
      }
      return
    }
    applyDefaultSellingPoints({ force })
    lastSellingPointsProductTitle.value = requestedTitle
    if (force) scriptCopySellingPointsTouched.value = false
  } catch (err) {
    console.error('generate selling points failed:', err)
    if (requestSeq === sellingPointsRequestSeq.value) {
      applyDefaultSellingPoints({ force })
      lastSellingPointsProductTitle.value = requestedTitle
      if (force) scriptCopySellingPointsTouched.value = false
    }
  } finally {
    if (requestSeq === sellingPointsRequestSeq.value) sellingPointsGenerating.value = false
  }
}

const handleProductTitleBlur = () => {
  const currentTitle = getNormalizedProductTitle()
  if (currentTitle === lastSellingPointsProductTitle.value) {
    generateDefaultSellingPoints()
    return
  }
  scriptCopySellingPointsTouched.value = false
  scriptCopyForm.value.selling_points = ''
  generateDefaultSellingPoints({ force: true })
}

const handleSellingPointsInput = () => {
  scriptCopySellingPointsTouched.value = true
  sellingPointsRequestSeq.value += 1
  sellingPointsGenerating.value = false
}

const appendSellingPointTag = (tag) => {
  scriptCopySellingPointsTouched.value = true
  const current = scriptCopyForm.value.selling_points.trim()
  const parts = current
    ? current.split(/[，,、\n]/).map((item) => item.trim()).filter(Boolean)
    : []
  if (parts.includes(tag)) return
  const next = [...parts, tag].join('、')
  scriptCopyForm.value.selling_points = next.slice(0, 200)
}

const confirmProductClassificationMismatch = async () => {
  const sourceClassification = getVersionProductClassification(scriptCopySourceVersion.value)
  const productClassification = inferScriptCopyProductClassification()
  if (!sourceClassification || !productClassification || sourceClassification === productClassification) return true

  try {
    await ElMessageBox.confirm(
      `参考视频产品分类是「${sourceClassification}」，当前商品更像「${productClassification}」。不同品类可能导致原脚本的场景、卖点和黄金3秒不完全适配，仍要继续生成吗？`,
      '产品分类不一致',
      {
        confirmButtonText: '继续生成',
        cancelButtonText: '返回修改',
        type: 'warning',
      },
    )
    return true
  } catch {
    return false
  }
}

const generateScriptCopy = async () => {
  if (!canSubmitScriptCopy.value) {
    ElMessage.warning('请至少选择或输入需要带货的商品，或上传产品图片')
    return
  }
  await generateDefaultSellingPoints({
    force: Boolean(
      getNormalizedProductTitle()
      && getNormalizedProductTitle() !== lastSellingPointsProductTitle.value,
    ),
  })
  const canContinue = await confirmProductClassificationMismatch()
  if (!canContinue) return

  scriptCopyLoading.value = true
  scriptCopyResult.value = null
  const fd = new FormData()
  fd.append('model', scriptCopyForm.value.model)
  if (scriptCopySourceModel.value) fd.append('source_model', scriptCopySourceModel.value)
  Object.entries(scriptCopyForm.value).forEach(([key, value]) => {
    if (key === 'model') return
    if (String(value || '').trim()) fd.append(key, String(value).trim())
  })
  scriptCopyImageFiles.value.forEach((file) => fd.append('product_images', file))

  try {
    const res = await axios.post(`/api/analyses/${activeAnalysisId.value}/script-copy`, fd, { timeout: 180000 })
    scriptCopyResult.value = res.data.data
    ElMessage.success('新脚本已生成')
  } catch (err) {
    console.error('generate script copy failed:', err)
    const detail = err?.response?.data?.detail || err?.response?.data?.msg || err?.message
    ElMessage.error(detail ? `脚本生成失败：${detail}` : '脚本生成失败')
  } finally {
    scriptCopyLoading.value = false
  }
}

const formatScriptCopyResultText = () => {
  if (!scriptCopyResult.value) return ''
  const strategy = scriptCopyResult.value.copy_strategy || {}
  const lines = [
    `复刻策略：${strategy.script_logic || '按源视频结构生成新脚本'}`,
    strategy.golden_3s_recreation ? `黄金3秒：${strategy.golden_3s_recreation}` : '',
    '',
  ].filter((line) => line !== '')
  ;(scriptCopyResult.value.shots || []).forEach((shot, index) => {
    lines.push(`分镜 ${shot.shot_index || index + 1} ${shot.title || ''}`)
    if (shot.visual_plan) lines.push(`画面：${shot.visual_plan}`)
    if (shot.voiceover) lines.push(`口播：${shot.voiceover}`)
    if (shot.screen_text) lines.push(`字幕：${shot.screen_text}`)
    if (shot.new_script) lines.push(`完整脚本：${shot.new_script}`)
    if (shot.shooting_notes) lines.push(`拍摄要点：${shot.shooting_notes}`)
    if (shot.conversion_point) lines.push(`转化作用：${shot.conversion_point}`)
    lines.push('')
  })
  if (scriptCopyResult.value.cta_options?.length) {
    lines.push(`CTA备选：${scriptCopyResult.value.cta_options.join(' / ')}`)
  }
  return lines.join('\n').trim()
}

const copyGeneratedScript = async () => {
  const text = formatScriptCopyResultText()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制生成脚本')
  } catch {
    ElMessage.warning('浏览器不允许直接复制，请手动选中结果文本复制')
  }
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
  revokeScriptCopyImagePreviews()
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

.copy-workspace {
  max-width: 1440px;
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

.copy-topbar {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-end;
  padding-bottom: 16px;
  border-bottom: 1px solid #d9e1ec;
}

.copy-topbar h2 {
  margin: 0;
  color: #172033;
  font-size: 24px;
  line-height: 1.25;
}

.copy-topbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.copy-page-grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  margin-top: 18px;
}

.copy-source-panel,
.copy-form-panel,
.copy-result-panel {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid #dfe6f0;
  border-radius: 8px;
}

.copy-source-panel {
  position: sticky;
  top: 20px;
  display: grid;
  gap: 14px;
  padding: 16px;
}

.copy-source-panel h3,
.copy-form-head h3,
.copy-result-head h3 {
  margin: 0;
  color: #1d2939;
  font-size: 18px;
  line-height: 1.35;
}

.copy-source-head,
.copy-result-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.copy-source-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.copy-hook-box,
.copy-strategy,
.copy-cta-box,
.viral-summary-box {
  padding: 12px;
  color: #475467;
  background: #f8fafc;
  border: 1px solid #e5ebf3;
  border-radius: 8px;
}

.copy-hook-box strong,
.copy-strategy strong,
.copy-cta-box strong,
.viral-summary-box strong {
  color: #1d2939;
  font-size: 13px;
}

.copy-hook-box p,
.copy-strategy p,
.copy-cta-box p,
.viral-summary-box p {
  margin: 6px 0 0;
  line-height: 1.65;
  font-size: 13px;
}

.viral-summary-box {
  margin-top: 10px;
}

.golden-script-highlight {
  padding: 1px 3px;
  color: #9f3412;
  background: #ffedd5;
  border-radius: 4px;
}

.copy-template-list {
  display: grid;
  gap: 10px;
}

.copy-template-item {
  padding: 10px 0;
  border-top: 1px solid #e5ebf3;
}

.copy-template-item span {
  display: block;
  margin-bottom: 4px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.copy-template-item strong {
  color: #1d2939;
  font-size: 14px;
}

.copy-template-item dl {
  display: grid;
  gap: 8px;
  margin: 8px 0 0;
}

.copy-template-item dl div {
  display: grid;
  gap: 3px;
}

.copy-template-item dt {
  color: #98a2b3;
  font-size: 11px;
  font-weight: 700;
}

.copy-template-item dd {
  margin: 0;
  color: #667085;
  line-height: 1.55;
  font-size: 12px;
}

.copy-main-panel {
  display: grid;
  gap: 18px;
}

.copy-form-panel,
.copy-result-panel {
  padding: 18px;
}

.copy-form-head,
.copy-result-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.copy-model-select {
  width: 100%;
}

.copy-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 14px;
}

.required-form-item :deep(.el-form-item__label)::before {
  content: "*";
  margin-right: 4px;
  color: #f04438;
}

.product-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  width: 100%;
}

.highlight-input-wrap {
  display: grid;
  gap: 8px;
  width: 100%;
}

.highlight-input-wrap :deep(.el-textarea__inner) {
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.highlight-input-wrap.is-generating :deep(.el-textarea__inner) {
  background: #f8fbff;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(43, 125, 233, 0.14);
}

.data-support-tip {
  width: fit-content;
  max-width: 100%;
  padding: 4px 8px;
  color: #7c3aed;
  background: #f1edff;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.35;
}

.selling-points-status {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  color: #174a7c;
  background: #eef6ff;
  border: 1px solid #b9d7f8;
  border-radius: 8px;
}

.selling-points-status strong {
  display: block;
  color: #174a7c;
  font-size: 13px;
  line-height: 1.35;
}

.selling-points-status p {
  margin: 2px 0 0;
  color: #52657a;
  font-size: 12px;
  line-height: 1.45;
}

.selling-points-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #b9d7f8;
  border-top-color: #2b7de9;
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

.selling-point-recommendations {
  display: grid;
  gap: 10px;
  margin: 4px 0 16px;
}

.selling-point-recommendations strong {
  color: #1d2939;
  font-size: 14px;
}

.selling-point-recommendations > div {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.selling-point-recommendations.is-generating .recommend-tag {
  opacity: 0.45;
  cursor: wait;
}

.recommend-skeleton-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.recommend-skeleton {
  width: 74px;
  height: 24px;
  overflow: hidden;
  position: relative;
  background: #eef2f7;
  border-radius: 999px;
}

.recommend-skeleton::after {
  content: "";
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.78), transparent);
  animation: shimmer 1.2s infinite;
}

.recommend-tag {
  cursor: pointer;
  border-color: #eaecf5;
  background: #f8f9fc;
  color: #344054;
}

.recommend-tag:hover {
  border-color: #b9d7f8;
  color: #175cd3;
}

.advanced-copy-settings {
  margin-top: 4px;
  border-top: 1px solid #e5ebf3;
  border-bottom: 1px solid #e5ebf3;
}

.advanced-copy-settings :deep(.el-collapse-item__header) {
  height: 40px;
  color: #667085;
  background: transparent;
  font-size: 13px;
  font-weight: 700;
}

.copy-upload-row {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(260px, 1.2fr);
  gap: 16px;
  align-items: start;
  padding-top: 8px;
}

.copy-upload-row strong {
  color: #1d2939;
}

.copy-upload-row p {
  margin: 6px 0 0;
  color: #667085;
  line-height: 1.6;
  font-size: 13px;
}

.copy-loading,
.copy-empty-result {
  display: grid;
  min-height: 220px;
  place-items: center;
  color: #667085;
  text-align: center;
}

.copy-loading {
  align-content: center;
  gap: 12px;
}

.copy-result-content {
  display: grid;
  gap: 12px;
}

.copy-section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-top: 2px;
}

.copy-section-title strong {
  color: #172033;
  font-size: 14px;
}

.copy-section-title span {
  color: #667085;
  font-size: 12px;
}

.copy-shot-card {
  padding: 14px;
  background: #ffffff;
  border: 1px solid #e5ebf3;
  border-radius: 8px;
}

.copy-shot-head {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.copy-shot-head span {
  padding: 3px 8px;
  color: #667085;
  background: #eef2f7;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.copy-shot-head strong {
  color: #172033;
}

.copy-shot-head em {
  color: #667085;
  font-size: 12px;
  font-style: normal;
}

.copy-hook-line {
  margin: 0 0 10px;
  padding: 8px 10px;
  color: #9f3412;
  background: #fff7ed;
  border-left: 3px solid #fb923c;
  line-height: 1.6;
  font-size: 12px;
}

.copy-shot-card dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.copy-shot-card dl div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
}

.copy-shot-card dt {
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.copy-shot-card dd {
  margin: 0;
  color: #344054;
  line-height: 1.65;
  font-size: 13px;
}

.copy-empty-shots {
  padding: 16px;
  color: #667085;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  font-size: 13px;
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

@keyframes shimmer {
  to {
    transform: translateX(100%);
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

.clickable-tag {
  cursor: pointer;
}

.hook-popover strong {
  display: block;
  color: #1d2939;
  font-size: 13px;
}

.hook-popover p {
  margin: 6px 0 12px;
  color: #475467;
  line-height: 1.6;
  font-size: 13px;
}

.hook-popover p:last-child {
  margin-bottom: 0;
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
  .topbar,
  .copy-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .tool-bar {
    justify-content: flex-start;
  }

  .analysis-shell {
    grid-template-columns: 1fr;
  }

  .copy-page-grid {
    grid-template-columns: 1fr;
  }

  .copy-source-panel {
    position: static;
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

  .copy-upload-row {
    grid-template-columns: 1fr;
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

  .copy-topbar-actions,
  .copy-form-head,
  .copy-result-head {
    align-items: stretch;
    flex-direction: column;
    width: 100%;
  }

  .copy-model-select {
    width: 100%;
  }

  .copy-form-grid {
    grid-template-columns: 1fr;
  }

  .product-picker {
    grid-template-columns: 1fr;
  }

  .copy-shot-card dl div {
    grid-template-columns: 1fr;
    gap: 3px;
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
