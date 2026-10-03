<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const marks = ref([])
const rolls = ref([])
const error = ref('')
const formError = ref('')
const busy = ref(false)
const stateFilter = ref('valid')

const form = reactive({
  rollId: null,
  code: '',
  notes: '',
})

const filteredRolls = computed(() =>
  [...rolls.value].sort((a, b) => a.id - b.id)
)

function rollLabel(roll) {
  const state = { raw: '原布', dipping: '浸渍中', cured: '已固化' }[roll.status] || roll.status
  return `${roll.rollCode} · ${roll.loftName} · ${state}`
}

async function load() {
  error.value = ''
  try {
    const params = stateFilter.value === 'all' ? {} : { state: stateFilter.value }
    const [m, r] = await Promise.all([
      api.get('/marks/', { params }),
      api.get('/rolls/'),
    ])
    marks.value = m.data.results || m.data
    rolls.value = r.data.results || r.data
    if (!form.rollId && rolls.value.length) form.rollId = rolls.value[0].id
  } catch {
    error.value = '客户画押加载失败'
  }
}

async function submit() {
  formError.value = ''
  if (!/^\d{6}$/.test(form.code)) {
    formError.value = '画押编号必须正好为 6 位数字'
    return
  }
  busy.value = true
  try {
    await api.post('/marks/', {
      rollId: form.rollId,
      code: form.code,
      notes: form.notes,
    })
    form.code = ''
    form.notes = ''
    stateFilter.value = 'valid'
    await load()
  } catch (e) {
    const data = e.response?.data
    formError.value =
      data?.code?.[0] ||
      data?.rollId?.[0] ||
      data?.detail ||
      '落下画押编号失败'
  } finally {
    busy.value = false
  }
}

async function revoke(mark) {
  if (!isAdmin.value) return
  formError.value = ''
  busy.value = true
  try {
    await api.post(`/marks/${mark.id}/revoke/`)
    await load()
  } catch (e) {
    formError.value = e.response?.data?.detail || '作废失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="marks-page">
    <h1>客户画押</h1>
    <p class="sub">
      已固化卷拨回原布前，客户须在此页落下 6 位数字画押编号；没有未作废编号一律挡住。
      作废仅管理员可操作，作废后该编号不能再放行。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>

    <form class="panel row" @submit.prevent="submit">
      <label>布卷
        <select v-model.number="form.rollId" required>
          <option v-for="r in filteredRolls" :key="r.id" :value="r.id">
            {{ rollLabel(r) }}{{ r.activeMarkCode ? '（已有有效画押）' : '' }}
          </option>
        </select>
      </label>
      <label>画押编号（6 位数字）
        <input
          v-model="form.code"
          inputmode="numeric"
          maxlength="6"
          pattern="\d{6}"
          placeholder="如 048215"
          required
        />
      </label>
      <label>备注
        <input v-model="form.notes" maxlength="200" />
      </label>
      <button class="btn" type="submit" :disabled="busy">落下编号</button>
    </form>

    <div class="mark-filter panel row">
      <span class="filter-label">筛选：</span>
      <button
        v-for="opt in [
          { v: 'valid', t: '有效' },
          { v: 'void', t: '已作废' },
          { v: 'all', t: '全部' },
        ]"
        :key="opt.v"
        type="button"
        class="btn"
        :class="['filter-btn', { secondary: stateFilter !== opt.v }]"
        @click="stateFilter = opt.v; load()"
      >
        {{ opt.t }}
      </button>
    </div>

    <table>
      <thead>
        <tr>
          <th>状态</th>
          <th>布卷</th>
          <th>帆布间</th>
          <th>画押编号</th>
          <th>画押时刻</th>
          <th>画押人</th>
          <th>作废时刻 / 人</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in marks" :key="m.id" :class="{ 'row-void': !!m.revokedAt }">
          <td>
            <span class="badge" :class="m.revokedAt ? 'badge-void' : 'badge-valid'">
              {{ m.revokedAt ? '已作废' : '有效' }}
            </span>
          </td>
          <td>{{ m.rollCode }}</td>
          <td>{{ m.loftName }}</td>
          <td class="mark-code">{{ m.code }}</td>
          <td>{{ new Date(m.signedAt).toLocaleString() }}</td>
          <td>{{ m.signedBy }}</td>
          <td>
            <template v-if="m.revokedAt">
              {{ new Date(m.revokedAt).toLocaleString() }} · {{ m.revokedBy }}
            </template>
            <span v-else class="hint">—</span>
          </td>
          <td>
            <button
              v-if="isAdmin && !m.revokedAt"
              class="btn danger"
              type="button"
              :disabled="busy"
              @click="revoke(m)"
            >
              作废
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!marks.length" class="hint" style="margin-top:12px">没有符合筛选条件的画押编号</p>
  </div>
</template>
