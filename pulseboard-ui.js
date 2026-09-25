(() => {
  const API = 'https://portfolio-pulseboard-demo.onrender.com/api/v1/demo';
  const TOKEN_KEY = 'pulseboard-demo-token-v1';
  const statuses = [
    { id: 'todo', title: 'К выполнению', next: 'Начать' },
    { id: 'doing', title: 'В работе', next: 'Завершить' },
    { id: 'done', title: 'Готово', next: null },
  ];
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);
  const filter = $('project-filter');
  const board = $('board');
  let token = localStorage.getItem(TOKEN_KEY);
  let data = { projects: [], tasks: [] };
  let ready = false;
  let busy = false;

  const toast = message => {
    document.querySelector('.toast')?.remove();
    const node = document.createElement('div'); node.className = 'toast'; node.setAttribute('role', 'status'); node.textContent = message;
    document.body.append(node); window.setTimeout(() => node.remove(), 2600);
  };
  const request = async (path, options = {}, retry = true) => {
    const response = await fetch(`${API}${path}`, { ...options, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
    if ((response.status === 401 || response.status === 410) && retry && path !== '/session') {
      await newSession();
      return request(path, options, false);
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `Ошибка API (${response.status})`);
    return payload;
  };
  const newSession = async () => {
    const response = await fetch(`${API}/session`, { method: 'POST' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `API недоступен (${response.status})`);
    token = payload.access_token;
    localStorage.setItem(TOKEN_KEY, token);
  };
  const setBusy = value => {
    busy = value;
    document.querySelectorAll('.board-actions button, #reset-demo, .move-task').forEach(button => { button.disabled = value; });
  };
  const fillProjectSelects = () => {
    const old = filter.value;
    filter.innerHTML = '<option value="all">Все проекты</option>' + data.projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
    filter.value = data.projects.some(p => p.id === old) || old === 'all' ? old : 'all';
    $('task-project').innerHTML = data.projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  };
  const render = () => {
    fillProjectSelects();
    const selected = filter.value;
    const shown = data.tasks.filter(t => selected === 'all' || t.project_id === selected);
    const done = shown.filter(t => t.status === 'done').length;
    $('board-stats').innerHTML = `<span><b>${shown.length}</b> задач</span><span><b>${done}</b> завершено</span>`;
    board.innerHTML = statuses.map(status => {
      const tasks = shown.filter(t => t.status === status.id);
      return `<section class="board-column" data-status="${status.id}" aria-label="${status.title}">
        <div class="column-heading"><div class="column-name"><span class="status-dot"></span>${status.title}</div><span class="task-count">${tasks.length}</span></div>
        <div class="task-list">${tasks.length ? tasks.map(task => {
          const project = data.projects.find(p => p.id === task.project_id);
          return `<article class="task-card"><h3>${esc(task.title)}</h3><span class="task-project">${esc(project?.name || 'Без проекта')}</span><div class="task-foot"><span>${status.id === 'done' ? 'Задача закрыта' : 'В списке команды'}</span>${status.next ? `<button class="move-task" data-move="${esc(task.id)}" ${busy ? 'disabled' : ''}>${status.next} →</button>` : `<button class="move-task" data-move="${esc(task.id)}" ${busy ? 'disabled' : ''}>Вернуть ↶</button>`}</div></article>`;
        }).join('') : '<div class="column-empty">Пока пусто</div>'}</div></section>`;
    }).join('');
    if (!data.projects.length) board.innerHTML = '<div class="no-projects"><b>Начните с проекта</b>Создайте проект, затем добавляйте в него задачи.</div>';
  };
  const loadBoard = async () => { data = await request('/board'); ready = true; render(); document.body.classList.remove('board-loading'); };
  const showError = error => { board.innerHTML = `<div class="no-projects"><b>Не удалось подключиться к доске</b>${esc(error.message)}<br><button class="button lime" id="retry-api">Повторить подключение</button></div>`; document.body.classList.remove('board-loading'); $('retry-api')?.addEventListener('click', initialize); };
  const initialize = async () => {
    if (busy) return;
    setBusy(true); document.body.classList.add('board-loading');
    try { if (!token) await newSession(); await loadBoard(); }
    catch (error) { showError(error); }
    finally { setBusy(false); if (!ready) document.body.classList.remove('board-loading'); }
  };

  $('new-project').addEventListener('click', () => projectDialog.showModal());
  const projectDialog = $('project-dialog');
  const taskDialog = $('task-dialog');
  $('new-task').addEventListener('click', () => { if (!data.projects.length) { projectDialog.showModal(); return; } taskDialog.showModal(); });
  document.querySelectorAll('[data-close], .dialog-close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  $('project-form').addEventListener('submit', async event => {
    event.preventDefault();
    const name = $('project-name').value.trim(); if (name.length < 2 || busy) return;
    setBusy(true);
    try { const project = await request('/projects', { method: 'POST', body: JSON.stringify({ name }) }); await loadBoard(); filter.value = project.id; render(); $('project-form').reset(); projectDialog.close(); toast('Проект сохранён в API'); }
    catch (error) { toast(error.message); }
    finally { setBusy(false); }
  });
  $('task-form').addEventListener('submit', async event => {
    event.preventDefault();
    const title = $('task-title').value.trim(); if (title.length < 2 || !data.projects.length || busy) return;
    setBusy(true);
    try { const task = await request('/tasks', { method: 'POST', body: JSON.stringify({ title, project_id: $('task-project').value }) }); await loadBoard(); filter.value = task.project_id; render(); $('task-form').reset(); taskDialog.close(); toast('Задача сохранена в API'); }
    catch (error) { toast(error.message); }
    finally { setBusy(false); }
  });
  board.addEventListener('click', async event => {
    const button = event.target.closest('[data-move]'); if (!button || busy) return;
    const task = data.tasks.find(item => item.id === button.dataset.move); if (!task) return;
    const index = statuses.findIndex(status => status.id === task.status);
    const status = statuses[index === statuses.length - 1 ? 0 : index + 1].id;
    setBusy(true);
    try { await request(`/tasks/${encodeURIComponent(task.id)}`, { method: 'PATCH', body: JSON.stringify({ status }) }); await loadBoard(); }
    catch (error) { toast(error.message); }
    finally { setBusy(false); }
  });
  filter.addEventListener('change', render);
  $('reset-demo').addEventListener('click', async () => {
    if (!window.confirm('Начать новую сессию с примерными проектами? Текущие данные этой демо-сессии будут удалены.')) return;
    setBusy(true);
    try { await request('/reset', { method: 'POST' }); await loadBoard(); toast('Пример восстановлен на сервере'); }
    catch (error) { toast(error.message); }
    finally { setBusy(false); }
  });
  initialize();
})();
