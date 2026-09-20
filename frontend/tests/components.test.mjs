import { mount } from '@vue/test-utils'
import ScheduleBoard from '../src/components/ScheduleBoard.vue'
import VenueFormModal from '../src/components/VenueFormModal.vue'
import BookingModalReal from '../src/components/BookingModal.vue'

;(window.__suite = (async () => {
  const t = new Date()
  const p = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate()
    ).padStart(2, '0')}`

  let pass = 0
  let fail = 0
  const check = (name, cond, extra = '') => {
    if (cond) { pass++; console.log('✓', name) } else { fail++; console.log('✗', name, extra) }
  }
  const flush = () => new Promise((r) => setTimeout(r, 30))

  const building = { id: 1, name: '汇智楼', code: 'HZ_A', floors: [{ id: 12, level: 2, name: '2F' }] }
  const venue = {
    id: 101, name: '第一会议室', room_no: 'A101', capacity: 12, venue_type: 'meeting_room',
    facilities: ['projector', 'whiteboard'], status: 'available', floor_id: 12,
    floor: { id: 12, level: 2, name: '2F' },
  }

  // ---------- 日视图 ----------
  const wrapper = mount(ScheduleBoard, { props: { building, venue } })
  await flush(); await flush()
  check('日视图渲染档期标题', wrapper.text().includes('研发晨会'))
  check('日视图渲染跨天场并标“跨天起”',
    wrapper.text().includes('产品封闭评审（跨天）') && wrapper.text().includes('跨天起'))
  check('显示门牌/楼层/容纳人数',
    wrapper.text().includes('A101') && wrapper.text().includes('2F') && wrapper.text().includes('12'))

  // ---------- 切周视图 ----------
  wrapper.findAll('button').find((b) => b.text().includes('周视图'))?.trigger('click')
  await flush(); await flush()
  check('周视图出现“跨2天”标记', wrapper.text().includes('跨2天'))
  check('周视图有周一和周日列头',
    wrapper.text().includes('周一') && wrapper.text().includes('周日'))
  check('周视图只有一条跨天记录（不被拆成两段）',
    wrapper.text().split('产品封闭评审（跨天）').length - 1 === 1)

  // 翻周 + 回到今天
  wrapper.findAll('button').find((b) => b.text().includes('下一周'))?.trigger('click')
  await flush(); await flush()
  wrapper.findAll('button').find((b) => b.text().includes('上一周'))?.trigger('click')
  await flush(); await flush()

  // ---------- BookingModal：成功 ----------
  async function fillBooking(modal, title, org, start, end) {
    const inputs = modal.findAll('input')
    await inputs[0].setValue(title)
    await inputs[1].setValue(org)
    await inputs[2].setValue(start)
    await inputs[3].setValue(end)
  }

  const okModal = mount(BookingModalReal, { props: { venue } })
  await fillBooking(okModal, '正常新会议', '测试员', `${p(t)}T18:00`, `${p(t)}T19:00`)
  await okModal.findAll('button')[1].trigger('click')
  await flush(); await flush()
  const postCalls = window.__calls.filter((c) => c.method === 'POST' && c.url.endsWith('/api/bookings'))
  check('成功路径：发出一次预订 POST 且载荷正确',
    postCalls.length === 1 &&
    postCalls[0].body.title === '正常新会议' &&
    postCalls[0].body.start_at === `${p(t)}T18:00:00` &&
    !okModal.text().includes('档期没有登记成功'))

  // ---------- BookingModal：冲突 ----------
  const cf = mount(BookingModalReal, { props: { venue } })
  await fillBooking(cf, '必撞的会', '测试员', `${p(t)}T09:30`, `${p(t)}T11:00`)
  await cf.findAll('button')[1].trigger('click')
  await flush()
  check('冲突时弹窗显示被谁占用',
    cf.text().includes('研发晨会') && cf.text().includes('行政部'))
  check('冲突时不发 created 事件', !cf.emitted('created'))

  // ---------- VenueFormModal：删除拦截 ----------
  const vf = mount(VenueFormModal, { props: { building, venue } })
  const delBtn = vf.findAll('button').find((b) => b.text().includes('删除场地'))
  check('编辑态出现删除按钮', !!delBtn)
  await delBtn.trigger('click')
  await flush()
  check('删除被拦时显示“2 场未结束的档期”原因',
    vf.text().includes('2 场未结束的档期'), vf.text())

  console.log(`\n组件测试：${pass} 通过 / ${fail} 失败`)
  return fail === 0
})())
