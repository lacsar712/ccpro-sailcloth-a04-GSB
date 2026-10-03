<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const signoffs = ref([])
const rolls = ref([])
const error = ref('')
const busy = ref(false)
const stateFilter = ref('all')

const form = reactive({
  rollId: null,
  code: '',
})

const isAdmin = computed(() => auth.user?.role === 'admin')

const statusLabel = { raw: '原布', dipping: '浸渍中', cured: '已固化' }

const rollOptions = computed(() =>
  rolls.value.map((r) => ({
    id: r.id,
    label: `${r.loftName} / ${r.rollCode}（${statusLabel[r.status] || r.status}）`,
    hasActive: !!r.activeSignOffCode,
  }))
)

const filters = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '有效' },
  { key: 'voided', label: '已作废' },
]

async function load() {
  error.value = ''
  try {
    const params = {}
    if (stateFilter.value !== 'all') params.state = stateFilter.value
    const [s, r] = await Promise.all([
      api.get('/signoffs/', { params }),
      api.get('/rolls/'),
    ])
    signoffs.value = s.data.results || s.data
    rolls.value = r.data.results || r.data
    if (!form.rollId && rolls.value.length) form.rollId = rolls.value[0].id
  } catch {
    error.value = '画押记录加载失败'
  }
}

function setFilter(key) {
  stateFilter.value = key
  load()
}

function fmt(dt) {
  return dt ? new Date(dt).toLocaleString() : '—'
}

async function submit() {
  error.value = ''
  if (!/^\d{6}$/.test(form.code)) {
    error.value = '画押编号必须正好 6 位数字'
    return
  }
  busy.value = true
  try {
    await api.post('/signoffs/', { rollId: form.rollId, code: form.code })
    form.code = ''
    await load()
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.rollId?.[0] ||
      data?.code?.[0] ||
      data?.detail ||
      '落下编号失败'
  } finally {
    busy.value = false
  }
}

async function voidSignOff(row) {
  error.value = ''
  busy.value = true
  try {
    await api.post(`/signoffs/${row.id}/void/`)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '作废失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>客户画押</h1>
    <p class="sub">已固化卷拨回原布前，客户须在此落下 6 位数字画押编号；同一卷未作废编号最多一条。作废仅管理员可操作，作废后不能再用于放行。</p>

    <div class="filter-bar">
      <button
        v-for="f in filters"
        :key="f.key"
        type="button"
        class="btn"
        :class="{ secondary: stateFilter !== f.key }"
        @click="setFilter(f.key)"
      >
        {{ f.label }}
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <form class="panel row" @submit.prevent="submit">
      <label>布卷
        <select v-model.number="form.rollId" required>
          <option v-for="o in rollOptions" :key="o.id" :value="o.id">
            {{ o.label }}{{ o.hasActive ? ' · 已有有效编号' : '' }}
          </option>
        </select>
      </label>
      <label>画押编号（6 位数字）
        <input
          v-model.trim="form.code"
          inputmode="numeric"
          maxlength="6"
          placeholder="例如 608821"
          required
        />
      </label>
      <button class="btn" type="submit" :disabled="busy">落下编号</button>
    </form>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>卷号</th>
          <th>画押编号</th>
          <th>画押时刻</th>
          <th>画押人</th>
          <th>状态</th>
          <th>作废时刻</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in signoffs" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>{{ row.rollCode }}</td>
          <td><strong>{{ row.code }}</strong></td>
          <td>{{ fmt(row.signedAt) }}</td>
          <td>{{ row.signedBy }}</td>
          <td>
            <span class="badge" :class="row.active ? 'badge-cured' : 'badge-raw'">
              {{ row.active ? '有效' : '已作废' }}
            </span>
          </td>
          <td>{{ fmt(row.voidedAt) }}</td>
          <td>
            <button
              v-if="row.active && isAdmin"
              class="btn secondary"
              type="button"
              :disabled="busy"
              @click="voidSignOff(row)"
            >
              作废
            </button>
            <span v-else-if="row.active" class="hint">仅管理员可作废</span>
          </td>
        </tr>
        <tr v-if="!signoffs.length">
          <td colspan="8" class="hint">暂无画押记录</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
