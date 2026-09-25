(() => {
  const KEY = 'pulseboard-sandbox-v3';
  const statuses = [
    { id: 'todo', title: 'К выполнению', next: 'Начать' },
    { id: 'doing', title: 'В работе', next: 'Завершить' },
    { id: 'done', title: 'Готово', next: null },
  ];
  const sample = () => ({
    projects: [
      { id: 'site', name: 'Сайт портфолио' },
      { id: 'assistant', name: 'AI-помощник' },
    ],
    tasks: [
      { id: 't1', project: 'site', title: 'Собрать обратную связь по макету', status: 'todo' },
      { id: 't2', project: 'site', title: 'Подготовить список страниц для запуска', status: 'doing' },
      { id: 't3', project: 'assistant', title: 'Проверить ответы по загруженным документам', status: 'todo' },
      { id: 't4', project: 'assistant', title: 'Добавить источники к ответам', status: 'done' },
    ],
  });
  const read = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY));
      if (saved && Array.isArray(saved.projects) && Array.isArray(saved.tasks)) return saved;
    } catch {}
    const seeded = sample();
    localStorage.setItem(KEY, JSON.stringify(seeded));
    return seeded;
  };
  let data = read();
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);
  const save = () => localStorage.setItem(KEY, JSON.stringify(data));
  const filter = $('project-filter');
  const board = $('board');
  const fillProjectSelects = () => {
    const old = filter.value;
    filter.innerHTML = '<option value="all">Все проекты</option>' + data.projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
    filter.value = data.projects.some(p => p.id === old) || old === 'all' ? old : 'all';
    $('task-project').innerHTML = data.projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  };
  const render = () => {
    fillProjectSelects();
    const selected = filter.value;
    const shown = data.tasks.filter(t => selected === 'all' || t.project === selected);
    const done = shown.filter(t => t.status === 'done').length;
    $('board-stats').innerHTML = `<span><b>${shown.length}</b> задач</span><span><b>${done}</b> завершено</span>`;
    board.innerHTML = statuses.map(status => {
      const tasks = shown.filter(t => t.status === status.id);
      return `<section class="board-column" data-status="${status.id}" aria-label="${status.title}">
        <div class="column-heading"><div class="column-name"><span class="status-dot"></span>${status.title}</div><span class="task-count">${tasks.length}</span></div>
        <div class="task-list">${tasks.length ? tasks.map(task => {
          const project = data.projects.find(p => p.id === task.project);
          return `<article class="task-card"><h3>${esc(task.title)}</h3><span class="task-project">${esc(project?.name || 'Без проекта')}</span><div class="task-foot"><span>${status.id === 'done' ? 'Задача закрыта' : 'В списке команды'}</span>${status.next ? `<button class="move-task" data-move="${esc(task.id)}">${status.next} →</button>` : `<button class="move-task" data-move="${esc(task.id)}">Вернуть ↶</button>`}</div></article>`;
        }).join('') : '<div class="column-empty">Пока пусто</div>'}</div></section>`;
    }).join('');
    if (!data.projects.length) board.innerHTML = '<div class="no-projects"><b>Начните с проекта</b>Создайте проект, затем добавляйте в него задачи.</div>';
  };
  const projectDialog = $('project-dialog');
  const taskDialog = $('task-dialog');
  $('new-project').addEventListener('click', () => projectDialog.showModal());
  $('new-task').addEventListener('click', () => {
    if (!data.projects.length) { projectDialog.showModal(); return; }
    taskDialog.showModal();
  });
  document.querySelectorAll('[data-close], .dialog-close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  $('project-form').addEventListener('submit', event => {
    event.preventDefault();
    const name = $('project-name').value.trim();
    if (name.length < 2) return;
    const projectId = crypto.randomUUID();
    data.projects.push({ id: projectId, name });
    filter.value = projectId;
    save(); render(); $('project-form').reset(); projectDialog.close(); toast('Проект создан');
  });
  $('task-form').addEventListener('submit', event => {
    event.preventDefault();
    const title = $('task-title').value.trim();
    if (title.length < 2 || !data.projects.length) return;
    const projectId = $('task-project').value;
    data.tasks.unshift({ id: crypto.randomUUID(), project: projectId, title, status: 'todo' });
    filter.value = projectId;
    save(); render(); $('task-form').reset(); taskDialog.close(); toast('Задача добавлена');
  });
  board.addEventListener('click', event => {
    const button = event.target.closest('[data-move]');
    if (!button) return;
    const task = data.tasks.find(item => item.id === button.dataset.move);
    if (!task) return;
    const index = statuses.findIndex(status => status.id === task.status);
    task.status = statuses[index === statuses.length - 1 ? 0 : index + 1].id;
    save(); render();
  });
  filter.addEventListener('change', render);
  $('reset-demo').addEventListener('click', () => {
    if (!window.confirm('Вернуть примерные проекты и задачи? Текущие данные песочницы будут заменены.')) return;
    data = sample(); save(); render(); toast('Пример восстановлен');
  });
  const toast = message => {
    document.querySelector('.toast')?.remove();
    const node = document.createElement('div'); node.className = 'toast'; node.setAttribute('role', 'status'); node.textContent = message;
    document.body.append(node); window.setTimeout(() => node.remove(), 2200);
  };
  render();
})();
