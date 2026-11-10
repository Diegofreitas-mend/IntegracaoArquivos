"use strict";

const icons = {
  home: '<path d="m3 10 9-7 9 7v10H3V10Z"/><path d="M9 20v-7h6v7"/>',
  bag: '<path d="M5 7h14l1 14H4L5 7Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  box: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="M3 8v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  arrows: '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.01"/>',
  refresh:
    '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
};

function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.info}</svg>`;
}

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});
const main = document.querySelector("main");
const modal = document.querySelector("#modal");
const routes = new Map([
  ["inicio", ["Visão geral", homePage]],
  ["nova-venda", ["Nova venda", newSalePage]],
  ["historico", ["Histórico de vendas", historyPage]],
  ["catalogo", ["Catálogo", catalogPage]],
  ["estoque", ["Estoque", inventoryPage]],
  ["integracao", ["Integração", integrationPage]],
]);
let state = null;
let cart = new Map();
let busy = false;
let lastResults = [];
let toastTimer;
let currentUser = null;
let latestSale = null;
let saleFilter = "todos";
let returnRoute = "inicio";

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
}

function currentRoute() {
  const route = location.hash.slice(1);
  return routes.has(route) ? route : "inicio";
}

async function request(path, data) {
  const options =
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        };
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/acesso/")) {
      showAccess(
        "entrar",
        "Sua sessão expirou. Entre novamente para continuar.",
      );
    }
    const error = new Error(
      result.erro || "Não foi possível concluir a operação.",
    );
    error.status = response.status;
    throw error;
  }
  return result;
}

function draftKey() {
  return `ve-pedido:${currentUser.usuario}`;
}

function saveDraft() {
  if (!currentUser) return;
  try {
    if (cart.size)
      sessionStorage.setItem(draftKey(), JSON.stringify([...cart]));
    else sessionStorage.removeItem(draftKey());
  } catch {
    /* O pedido continua funcionando quando o armazenamento é bloqueado. */
  }
  updateDraftIndicator();
}

function restoreDraft() {
  try {
    const entries = JSON.parse(sessionStorage.getItem(draftKey()) || "[]");
    cart = new Map(
      entries.filter(
        ([id, quantity]) =>
          Number.isSafeInteger(id) &&
          Number.isSafeInteger(quantity) &&
          quantity > 0,
      ),
    );
  } catch {
    cart = new Map();
  }
}

function updateDraftIndicator() {
  const indicator = document.querySelector("#nav-cart");
  const count = [...cart.values()].reduce((sum, quantity) => sum + quantity, 0);
  indicator.textContent = count;
  indicator.hidden = count === 0;
}

function showAccess(modo = "entrar", mensagem = "") {
  if (currentUser) returnRoute = currentRoute();
  modo = modo === "cadastrar" ? "cadastrar" : "entrar";
  currentUser = null;
  state = null;
  cart.clear();
  latestSale = null;
  lastResults = [];
  saleFilter = "todos";
  if (modal.open) modal.close();
  document.querySelector(".app-header").hidden = true;
  document.querySelector(".app-sidebar").hidden = true;
  closeNavigation();
  document.querySelector("#notifications").replaceChildren();
  document.body.classList.add("access-screen");
  main.removeAttribute("aria-busy");
  main.innerHTML = accessPage(modo, mensagem);
  history.replaceState(
    null,
    "",
    `#${modo === "cadastrar" ? "cadastro" : "entrar"}`,
  );
  document.title = `${modo === "cadastrar" ? "Criar conta" : "Entrar"} · Arvendro Gestão`;
}

async function authenticate(form) {
  if (busy || !form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form));
  const errorField = document.querySelector("#access-error");
  errorField.textContent = "";
  if (form.dataset.auth === "cadastrar" && data.senha !== data.confirmacao) {
    errorField.textContent = "As senhas não coincidem.";
    form.elements.confirmacao.focus();
    return;
  }
  delete data.confirmacao;
  data.usuario = data.usuario.trim();
  setBusy(true);
  const button = form.querySelector("button[type=submit]");
  const originalLabel = button.textContent;
  button.textContent =
    form.dataset.auth === "cadastrar" ? "Cadastrando…" : "Entrando…";
  try {
    const result = await request(`/api/acesso/${form.dataset.auth}`, data);
    currentUser = result.usuario;
    history.replaceState(null, "", `#${returnRoute}`);
    document.querySelector("#notifications").replaceChildren();
    restoreDraft();
    await refresh();
  } catch (error) {
    if (currentUser) renderLoadError(error);
    else errorField.textContent = error.message;
  } finally {
    button.textContent = originalLabel;
    setBusy(false);
  }
}

async function initialize() {
  try {
    const route = location.hash.slice(1);
    if (routes.has(route)) returnRoute = route;
    const session = await request("/api/sessao");
    if (!session.usuario) {
      showAccess(route === "cadastro" ? "cadastrar" : "entrar");
      return;
    }
    currentUser = session.usuario;
    if (!routes.has(route)) history.replaceState(null, "", `#${returnRoute}`);
    restoreDraft();
    await refresh();
  } catch (error) {
    if (error.status !== 401) renderLoadError(error);
  }
}

function renderLoadError(error) {
  main.removeAttribute("aria-busy");
  main.innerHTML = `<div class="panel empty-page">${icon("info")}<h2>Não foi possível carregar os dados.</h2><p>${escapeHtml(error.message)}</p><button data-action="refresh">Tentar novamente</button></div>`;
}

async function refresh() {
  state = await request("/api/estado");
  // Atualizações de catálogo não apagam o carrinho. A confirmação usa os valores atuais.
  for (const id of cart.keys()) {
    if (!state.produtos.some((product) => product.produto_id === id))
      cart.delete(id);
  }
  saveDraft();
  render();
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  document.querySelector("#notifications").innerHTML =
    `<div class="toast ${error ? "error" : ""}">${icon(error ? "info" : "check")}<span>${escapeHtml(message)}</span></div>`;
  toastTimer = setTimeout(
    () => {
      document.querySelector("#notifications").replaceChildren();
    },
    error ? 10000 : 6000,
  );
}

function setBusy(value) {
  busy = value;
  document.body.classList.toggle("busy", value);
  document
    .querySelectorAll("button[data-action], button[type=submit]")
    .forEach((button) => {
      if (value) {
        button.dataset.previousDisabled = String(button.disabled);
        button.disabled = true;
      } else if (button.dataset.previousDisabled !== undefined) {
        button.disabled = button.dataset.previousDisabled === "true";
        delete button.dataset.previousDisabled;
      }
    });
}

async function mutate(path, data, afterSuccess) {
  if (busy) return;
  setBusy(true);
  try {
    const result = await request(path, data);
    if (afterSuccess) afterSuccess(result);
    if (result.resultados) lastResults = result.resultados;
    await refresh();
    const errors =
      result.resultados?.filter((item) => item.status !== "processado")
        .length || 0;
    toast(
      errors
        ? `${result.mensagem} ${errors} arquivo(s) precisam de atenção. Veja o resultado na integração.`
        : result.mensagem,
      errors > 0 || result.aviso,
    );
    return result;
  } catch (error) {
    if (!currentUser) return;
    const formError = modal.open && document.querySelector("#form-error");
    if (formError) formError.textContent = error.message;
    else toast(error.message, true);
  } finally {
    setBusy(false);
  }
}

function heading(title, description = "", action = "") {
  return `
    <div class="page-heading">
      <div><h1>${title}</h1>${description ? `<p class="subtitle">${description}</p>` : ""}</div>
      ${action ? `<div class="page-actions">${action}</div>` : ""}
    </div>`;
}

function metric(label, value) {
  return `<div class="metric"><span class="metric-label">${label}</span><strong class="metric-value">${value}</strong></div>`;
}

function salesMetrics() {
  const today = new Date().toLocaleDateString("pt-BR");
  const sales = state.vendas.filter(
    (sale) => new Date(sale.data_hora).toLocaleDateString("pt-BR") === today,
  );
  const total =
    sales.reduce((sum, sale) => sum + Math.round(sale.total * 100), 0) / 100;
  const pending = state.vendas.filter((sale) =>
    ["pendente", "exportacao_pendente"].includes(sale.status),
  ).length;
  return `<div class="metrics" aria-label="Resumo de vendas">${metric("Vendas hoje", sales.length)}${metric("Valor registrado hoje", money.format(total))}${metric("Aguardando estoque", pending)}</div>`;
}

function search(placeholder) {
  return `<label class="search">${icon("search")}<input type="search" id="search" placeholder="${placeholder}" aria-label="${placeholder}" autocomplete="off"></label>`;
}

function productSearch(product) {
  return escapeHtml(
    `${product.nome} ${product.produto_id}`.toLocaleLowerCase("pt-BR"),
  );
}

function productTable(catalog = false) {
  const rows = state.produtos
    .map((product) => {
      const id = product.produto_id;
      const disabled = product.disponivel <= 0 || product.preco === null;
      const action = catalog
        ? `<button class="small" data-action="price" data-id="${id}">Editar preço</button>`
        : `<button class="small add-button" data-action="add" data-id="${id}" aria-label="Adicionar ${escapeHtml(product.nome)}" ${disabled ? "disabled" : ""}>${icon("plus")}Adicionar</button>`;
      return `
      <tr data-search="${productSearch(product)}">
        <td class="reference">${String(id).padStart(3, "0")}</td>
        <td class="product-name"><strong>${escapeHtml(product.nome)}</strong>${product.preco === null ? '<small class="missing-price">Preço não cadastrado</small>' : ""}</td>
        <td class="numeric" data-label="Disponível">${product.disponivel}<span class="unit"> un.</span></td>
        <td class="numeric price-cell" data-label="Preço">${product.preco === null ? "—" : money.format(product.preco)}</td>
        <td class="row-action">${action}</td>
      </tr>`;
    })
    .join("");
  return `
    <div class="table-scroll panel product-table" data-products>
      <table>
        <thead><tr><th>Código</th><th>Produto</th><th class="numeric">Disponível</th><th class="numeric">Preço</th><th><span class="sr-only">Ação</span></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="no-results" id="no-results" hidden>Nenhum produto encontrado.</p>
    </div>`;
}

function cartEntries() {
  return [...cart].map(([id, quantity]) => ({
    product: state.produtos.find((p) => p.produto_id === id),
    quantity,
  }));
}

function cartItem({ product, quantity }) {
  const id = product.produto_id;
  return `
    <div class="cart-item">
      <div class="cart-item-top">
        <strong>${escapeHtml(product.nome)}</strong>
        <button class="icon-button" data-action="remove" data-id="${id}" aria-label="Remover ${escapeHtml(product.nome)}">${icon("close")}</button>
      </div>
      <div class="cart-item-bottom">
        <div class="quantity-control">
          <button data-action="decrease" data-id="${id}" aria-label="Diminuir quantidade de ${escapeHtml(product.nome)}">−</button>
          <input type="number" min="1" max="${product.disponivel}" step="1" value="${quantity}" data-quantity="${id}" aria-label="Quantidade de ${escapeHtml(product.nome)}">
          <button data-action="add" data-id="${id}" aria-label="Aumentar quantidade de ${escapeHtml(product.nome)}">+</button>
        </div>
        <strong>${money.format((Math.round((product.preco || 0) * 100) * quantity) / 100)}</strong>
      </div>
      <small class="unit-price">${money.format(product.preco || 0)} / un.${quantity > product.disponivel ? " · Ajuste a quantidade: saldo alterado." : ""}</small>
    </div>`;
}

function orderPanel() {
  const entries = cartEntries();
  const quantity = entries.reduce((sum, item) => sum + item.quantity, 0);
  const total =
    entries.reduce(
      (sum, { product, quantity: count }) =>
        sum + Math.round((product.preco || 0) * 100) * count,
      0,
    ) / 100;
  const valid =
    entries.length &&
    entries.every(
      ({ product, quantity: count }) =>
        product.preco !== null && count <= product.disponivel,
    );
  return `
    <aside class="order-panel" aria-label="Resumo da venda">
      <div class="order-heading"><h2>Pedido atual</h2><span>${quantity} ${quantity === 1 ? "item" : "itens"}</span></div>
      ${entries.length ? `<div class="order-items">${entries.map(cartItem).join("")}</div>` : '<div class="empty-cart"><p>Nenhum produto adicionado.</p></div>'}
      <div class="order-summary">
        <div class="summary-total"><span>Total</span><strong>${money.format(total)}</strong></div>
        <button class="primary checkout-button" data-action="checkout" ${valid ? "" : "disabled"}>Registrar venda</button>
        <p class="order-footnote">O estoque será atualizado após a sincronização.</p>
      </div>
    </aside>`;
}

function badge(status) {
  const labels = {
    processado: ["Processada", ""],
    pendente: ["Aguardando estoque", "pending"],
    erro: ["Rejeitada", "error"],
    exportacao_pendente: ["Exportação pendente", "error"],
  };
  const [label, style] = labels[status] || ["Pendente", "neutral"];
  return `<span class="badge ${style}">${label}</span>`;
}

function salesTable(sales) {
  if (!sales.length)
    return '<div class="panel table-empty">Nenhuma venda registrada.</div>';
  const rows = sales
    .map(
      (sale) => `
    <tr data-status="${sale.status}" data-search="${escapeHtml(`${sale.venda_id} ${sale.itens.map((item) => item.nome).join(" ")}`.toLocaleLowerCase("pt-BR"))}">
      <td class="reference">#${sale.venda_id}</td>
      <td>${escapeHtml(dateTime.format(new Date(sale.data_hora)))}</td>
      <td class="numeric">${sale.itens.reduce((sum, item) => sum + item.quantidade, 0)}</td>
      <td class="numeric price-cell">${money.format(sale.total)}</td>
      <td>${badge(sale.status)}</td>
      <td class="row-action"><button class="text-button" data-action="detail" data-id="${sale.venda_id}" aria-label="Ver venda ${sale.venda_id}">Detalhes</button></td>
    </tr>`,
    )
    .join("");
  return `<div class="panel table-scroll"><table><thead><tr><th>Venda</th><th>Data e hora</th><th class="numeric">Itens</th><th class="numeric">Total</th><th>Estoque</th><th><span class="sr-only">Detalhes</span></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function newSalePage() {
  if (latestSale) return saleConfirmation();
  return `
    ${heading("Nova venda", "Selecione os produtos e informe as quantidades.")}
    <div class="sale-layout">
      <section aria-label="Produtos disponíveis">
        <div class="section-heading"><h2>Produtos <span class="count">${state.produtos.length}</span></h2>${search("Buscar produto ou código")}</div>
        ${productTable()}
        <p class="data-note">O disponível desconta os itens de vendas ainda não processadas.</p>
      </section>
      ${orderPanel()}
    </div>
    <section class="recent">
      <div class="section-heading"><h2>Últimas vendas</h2><a class="link" href="#historico">Ver histórico</a></div>
      ${salesTable(state.vendas.slice(0, 5))}
    </section>`;
}

function historyPage() {
  return `
    ${heading("Histórico de vendas", "Pedidos registrados e situação no estoque.", `<button data-action="refresh">${icon("refresh")}Atualizar</button>`)}
    ${salesMetrics()}
    <div class="section-heading"><h2>Registros <span class="count">${state.vendas.length}</span></h2>${search("Buscar venda ou produto")}</div>
    <div class="table-filters" role="group" aria-label="Filtrar vendas">${[
      ["todos", "Todas"],
      ["pendente", "Pendentes"],
      ["processado", "Processadas"],
      ["erro", "Com erro"],
    ]
      .map(
        ([value, label]) =>
          `<button data-filter="${value}" aria-pressed="${saleFilter === value}">${label}</button>`,
      )
      .join("")}</div>
    ${salesTable(state.vendas)}
    <p class="no-results" id="no-results" hidden>Nenhuma venda encontrada.</p>`;
}

function catalogPage() {
  return `
    ${heading("Catálogo de produtos", "Preços de venda e saldo disponível.", `<button class="primary" data-action="new-product">${icon("plus")}Novo produto</button>`)}
    <div class="section-heading"><h2>Produtos <span class="count">${state.produtos.length}</span></h2>${search("Buscar produto ou código")}</div>
    ${productTable(true)}
    <p class="data-note">A alteração de preço vale para as próximas vendas. Os pedidos registrados mantêm o valor original.</p>`;
}

function inventoryRow(product) {
  return `
    <tr data-search="${productSearch(product)}">
      <td class="reference">${String(product.produto_id).padStart(3, "0")}</td>
      <td class="product-name"><strong>${escapeHtml(product.nome)}</strong></td>
      <td class="numeric" data-label="Em estoque">${product.quantidade}</td>
      <td class="numeric" data-label="Reservado">${product.reservado}</td>
      <td class="numeric" data-label="Disponível"><strong>${product.disponivel}</strong></td>
      <td class="stock-status"><span class="badge ${product.quantidade <= 10 ? "pending" : "neutral"}">${product.quantidade === 0 ? "Sem estoque" : product.quantidade <= 10 ? "Saldo baixo" : "Regular"}</span></td>
      <td class="row-action"><button class="small" data-action="restock" data-id="${product.produto_id}">Repor</button></td>
    </tr>`;
}

function inventoryPage() {
  const total = state.produtos.reduce(
    (sum, product) => sum + product.quantidade,
    0,
  );
  const reserved = state.produtos.reduce(
    (sum, product) => sum + product.reservado,
    0,
  );
  const low = state.produtos.filter(
    (product) => product.quantidade <= 10,
  ).length;
  const pending = state.arquivos.saida.length + state.arquivos.entrada.length;
  return `
    ${heading("Estoque", "Saldos, reservas e reposição de produtos.", `<button data-action="sync">${icon("refresh")}Sincronizar vendas</button><button class="primary" data-action="new-product">${icon("plus")}Novo produto</button>`)}
    <div class="metrics">${metric("Produtos cadastrados", state.produtos.length)}${metric("Unidades em estoque", total)}${metric("Unidades reservadas", reserved)}${metric("Produtos com saldo baixo", low)}</div>
    ${pending ? `<div class="notice"><span>${pending} arquivo(s) aguardando processamento.</span><a href="#integracao" class="link">Ver integração</a></div>` : ""}
    <div class="section-heading"><h2>Produtos</h2>${search("Buscar no estoque")}</div>
    <div class="panel table-scroll inventory-table">
      <table><thead><tr><th>Código</th><th>Produto</th><th class="numeric">Em estoque</th><th class="numeric">Reservado</th><th class="numeric">Disponível</th><th>Situação</th><th><span class="sr-only">Reposição</span></th></tr></thead><tbody>${state.produtos.map(inventoryRow).join("")}</tbody></table>
      <p class="no-results" id="no-results" hidden>Nenhum produto encontrado.</p>
    </div>
    <p class="data-note">Saldo baixo: até 10 unidades em estoque. As reservas são liberadas após o processamento ou a rejeição da venda.</p>`;
}

function fileGroup(key, title, description) {
  const files = state.arquivos[key];
  return `
    <section class="file-panel">
      <h2>${title}<span class="file-count">${files.length}</span></h2>
      <p>${description}</p>
      <div class="file-list">${files.length ? files.map((file) => `<div>${escapeHtml(file)}</div>`).join("") : '<div class="no-files">Nenhum arquivo.</div>'}</div>
    </section>`;
}

function processingResults() {
  if (!lastResults.length) return "";
  return `
    <section class="recent">
      <div class="section-heading"><h2>Resultado do processamento</h2></div>
      <div class="panel table-scroll"><table><thead><tr><th>Arquivo</th><th>Resultado</th><th>Detalhe</th></tr></thead>
        <tbody>${lastResults.map((result) => `<tr><td class="filename">${escapeHtml(result.arquivo)}</td><td><span class="badge ${result.status === "processado" ? "" : "error"}">${escapeHtml(result.status)}</span></td><td class="result-message">${escapeHtml(result.motivo || "Estoque atualizado.")}</td></tr>`).join("")}</tbody>
      </table></div>
    </section>`;
}

function movementsTable() {
  if (!state.movimentacoes.length)
    return '<div class="panel table-empty">Nenhum movimento processado.</div>';
  const rows = state.movimentacoes
    .slice(0, 10)
    .map(
      (movement) => `
    <tr><td class="reference">#${escapeHtml(movement.venda_id)}</td><td class="filename">${escapeHtml(movement.arquivo)}</td><td>${escapeHtml(dateTime.format(new Date(movement.processado_em)))}</td><td>${badge("processado")}</td></tr>`,
    )
    .join("");
  return `<div class="panel table-scroll"><table><thead><tr><th>Venda</th><th>Arquivo</th><th>Processado em</th><th>Situação</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function integrationPage() {
  return `
    ${heading("Integração", "Transferência de vendas e processamento do estoque.", `<button data-action="refresh">${icon("refresh")}Atualizar</button><button class="primary" data-action="sync">${icon("arrows")}Sincronizar vendas</button>`)}
    <div class="integration-grid">
      ${fileGroup("saida", "Saída", "Vendas aguardando transferência")}
      ${fileGroup("entrada", "Entrada", "Arquivos recebidos pelo estoque")}
      ${fileGroup("processados", "Processados", "Baixas confirmadas no estoque")}
      ${fileGroup("erros", "Erros", "Arquivos rejeitados ou duplicados")}
    </div>
    <div class="processing-bar"><p>Para processar apenas os arquivos já recebidos na entrada:</p><button data-action="process">Processar entrada</button></div>
    ${processingResults()}
    <section class="recent"><div class="section-heading"><h2>Últimos movimentos</h2></div>${movementsTable()}</section>`;
}

function homePage() {
  const pending = state.arquivos.saida.length + state.arquivos.entrada.length;
  const exportPending = state.vendas.filter(
    (sale) => sale.status === "exportacao_pendente",
  ).length;
  const missingPrices = state.produtos.filter(
    (product) => product.preco === null,
  ).length;
  const low = state.produtos.filter((product) => product.quantidade <= 10);
  const pendingTotal = pending + exportPending;
  const integrationLabel = pendingTotal
    ? `${pendingTotal} ${pendingTotal === 1 ? "arquivo" : "arquivos"} para integrar`
    : "Integração em dia";
  const errorsLabel = state.arquivos.erros.length
    ? `${state.arquivos.erros.length} ${state.arquivos.erros.length === 1 ? "arquivo com erro" : "arquivos com erro"}`
    : "Nenhum arquivo com erro";
  const stockLabel = low.length
    ? `${low.length} ${low.length === 1 ? "produto" : "produtos"} com saldo baixo`
    : "Estoque regular";
  const date = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
  return `
    ${heading("Visão geral", date, '<a class="button primary" href="#nova-venda">Nova venda</a>')}
    ${salesMetrics()}
    <div class="home-layout">
      <section>
        <div class="section-heading"><h2>Vendas recentes</h2><a href="#historico" class="link">Ver histórico</a></div>
        ${salesTable(state.vendas.slice(0, 5))}
        ${cart.size ? '<a class="draft-link" href="#nova-venda">Continuar o pedido em andamento <span aria-hidden="true">→</span></a>' : ""}
      </section>
      <aside class="home-tasks">
        <h2>Pendências</h2>
        <div class="task-row"><div><strong>${integrationLabel}</strong><p>${pendingTotal ? "Atualize o estoque com as vendas registradas." : "Nenhuma venda aguardando processamento."}</p></div>${pendingTotal ? '<button class="small" data-action="sync">Sincronizar</button>' : '<span class="task-ok">Em dia</span>'}</div>
        <div class="task-row"><div><strong>${errorsLabel}</strong><p>Arquivos rejeitados ou duplicados.</p></div><a href="#integracao" class="link">Ver</a></div>
        ${missingPrices ? `<div class="task-row"><div><strong>${missingPrices} ${missingPrices === 1 ? "produto" : "produtos"} sem preço</strong><p>Defina o preço antes de vender.</p></div><a href="#catalogo" class="link">Corrigir</a></div>` : ""}
        <div class="task-row"><div><strong>${stockLabel}</strong><p>${low.length ? escapeHtml(low.map((product) => product.nome).join(", ")) : "Todos os produtos têm mais de 10 unidades."}</p></div><a href="#estoque" class="link">Ver</a></div>
      </aside>
    </div>`;
}

function saleConfirmation() {
  const sale = state.vendas.find((item) => item.venda_id === latestSale);
  if (!sale) {
    latestSale = null;
    return newSalePage();
  }
  const pending = ["pendente", "exportacao_pendente"].includes(sale.status);
  const quantity = sale.itens.reduce((sum, item) => sum + item.quantidade, 0);
  return `
    ${heading("Venda registrada", "O pedido foi salvo no histórico.")}
    <section class="sale-confirmation" aria-label="Venda registrada">
      <div class="confirmation-heading"><div><span class="confirmation-label">PEDIDO</span><h2>#${sale.venda_id}</h2></div>${badge(sale.status)}</div>
      <ul class="confirmation-items">${sale.itens.map((item) => `<li><span>${escapeHtml(item.nome)} <small>${item.quantidade} × ${money.format(item.preco)}</small></span><strong>${money.format(item.subtotal)}</strong></li>`).join("")}</ul>
      <div class="confirmation-total"><span>${quantity} ${quantity === 1 ? "item" : "itens"}</span><strong>${money.format(sale.total)}</strong></div>
      <div class="confirmation-next"><strong>${pending ? "Próxima etapa: atualizar o estoque" : sale.status === "processado" ? "Estoque atualizado" : "A integração precisa de atenção"}</strong><p>${pending ? "Os itens já estão reservados. Sincronize para confirmar a baixa no estoque." : sale.status === "processado" ? "A baixa dos produtos foi confirmada. Você já pode iniciar outro pedido." : "Consulte o resultado na integração para verificar o motivo da rejeição."}</p></div>
      <div class="confirmation-actions">${pending ? '<button class="primary" data-action="sync">Atualizar estoque agora</button>' : sale.status === "erro" ? '<a class="button" href="#integracao">Ver integração</a>' : ""}<button class="${pending ? "" : "primary"}" data-action="new-sale">Nova venda</button><button class="text-button" data-action="detail" data-id="${sale.venda_id}">Ver detalhes</button></div>
    </section>`;
}

function applyFilters() {
  const query = (document.querySelector("#search")?.value || "")
    .trim()
    .toLocaleLowerCase("pt-BR");
  const scope =
    currentRoute() === "nova-venda"
      ? main.querySelector("[data-products]")
      : main;
  if (!scope) return;
  let visible = 0;
  scope.querySelectorAll("[data-search]").forEach((item) => {
    const statusMatches =
      currentRoute() !== "historico" ||
      saleFilter === "todos" ||
      (saleFilter === "pendente"
        ? ["pendente", "exportacao_pendente"].includes(item.dataset.status)
        : saleFilter === "erro"
          ? ["erro", "exportacao_pendente"].includes(item.dataset.status)
          : item.dataset.status === saleFilter);
    item.hidden = !item.dataset.search.includes(query) || !statusMatches;
    if (!item.hidden) visible++;
  });
  const empty = document.querySelector("#no-results");
  if (empty) empty.hidden = visible > 0 || (!query && saleFilter === "todos");
  document
    .querySelectorAll("[data-filter]")
    .forEach((button) =>
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.filter === saleFilter),
      ),
    );
}

function render() {
  if (!state || !currentUser) return;
  document.body.classList.remove("access-screen");
  document.querySelector(".app-header").hidden = false;
  document.querySelector(".app-sidebar").hidden = false;
  document.querySelector(".app-sidebar").inert =
    window.matchMedia("(max-width: 850px)").matches &&
    !document.body.classList.contains("navigation-open");
  document.querySelector("#account-name").textContent = currentUser.nome;
  document.querySelector("#account-login").textContent =
    `@${currentUser.usuario}`;
  document.querySelector("#account-avatar").textContent = currentUser.nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((name) => name[0])
    .join("")
    .toUpperCase();
  main.removeAttribute("aria-busy");
  const route = currentRoute();
  const [title, page] = routes.get(route);
  main.innerHTML = page();
  document.querySelectorAll("[data-route]").forEach((link) => {
    const active = link.dataset.route === route;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document
    .querySelector("[data-route].active")
    ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  document.querySelector("#breadcrumb").textContent = title;
  document.title = `${title} · Arvendro Gestão`;
  const pending = state.arquivos.saida.length + state.arquivos.entrada.length;
  const count = document.querySelector("#nav-pending");
  count.textContent = pending;
  count.hidden = pending === 0;
  updateDraftIndicator();
  if (route === "historico") applyFilters();
}

function updateCart(id, quantity) {
  const product = state.produtos.find((item) => item.produto_id === id);
  if (!product) return;
  if (!Number.isSafeInteger(quantity) || quantity < 0) {
    toast("Informe uma quantidade inteira maior que zero.", true);
    return;
  }
  if (quantity > product.disponivel) {
    toast(
      `Disponível para ${product.nome}: ${product.disponivel} unidade(s).`,
      true,
    );
    return;
  }
  if (quantity === 0) cart.delete(id);
  else cart.set(id, quantity);
  saveDraft();
  const panel = document.querySelector(".order-panel");
  if (panel) panel.outerHTML = orderPanel();
}

function showModal(title, description, content) {
  document.querySelector("#modal-content").innerHTML =
    `<div class="modal-heading"><h2>${title}</h2><button class="icon-button" data-action="close" aria-label="Fechar">${icon("close")}</button></div><p class="modal-description">${description}</p>${content}`;
  modal.showModal();
}

function showForm(kind, id) {
  const product = state.produtos.find((item) => item.produto_id === id);
  let title, description, fields;
  if (kind === "new-product") {
    title = "Novo produto";
    description =
      "Cadastre o produto e seu saldo inicial. O preço pode ser definido no catálogo de vendas.";
    const nextId =
      Math.max(0, ...state.produtos.map((item) => item.produto_id)) + 1;
    fields = `<label class="field">Código do produto<input name="produto_id" type="number" min="1" max="2147483647" step="1" value="${nextId}" required></label><label class="field">Nome do produto<input name="nome" maxlength="100" placeholder="Ex.: Webcam" required></label><label class="field">Quantidade inicial<input name="quantidade" type="number" min="0" max="1000000" step="1" value="0" required></label>`;
  } else if (kind === "restock") {
    title = "Repor estoque";
    description = `Reposição de ${escapeHtml(product.nome)}. Saldo atual: ${product.quantidade} unidade(s).`;
    fields = `<input type="hidden" name="produto_id" value="${id}"><label class="field">Quantidade a adicionar<input name="quantidade" type="number" min="1" max="1000000" step="1" placeholder="Ex.: 10" required autofocus></label>`;
  } else {
    title = "Editar preço";
    description = `Defina o preço de venda de ${escapeHtml(product.nome)}.`;
    fields = `<input type="hidden" name="produto_id" value="${id}"><label class="field">Preço de venda (R$)<input name="preco" type="number" min="0.01" max="9999999.99" step="0.01" value="${product.preco ?? ""}" required autofocus><small>Use até duas casas decimais.</small></label>`;
  }
  showModal(
    title,
    description,
    `<form data-form="${kind}">${fields}<p class="form-error" id="form-error" role="alert"></p><div class="form-actions"><button type="button" data-action="close">Cancelar</button><button class="primary" type="submit">${icon("check")}Salvar</button></div></form>`,
  );
}

function showSale(id) {
  const sale = state.vendas.find((item) => item.venda_id === id);
  showModal(
    `Venda #${sale.venda_id}`,
    "Itens e valores do pedido.",
    `<div class="detail-meta">${escapeHtml(dateTime.format(new Date(sale.data_hora)))} · ${badge(sale.status)}</div><ul class="detail-items">${sale.itens.map((item) => `<li><span><strong>${escapeHtml(item.nome)}</strong><small>${item.quantidade} × ${money.format(item.preco)}</small></span><strong>${money.format(item.subtotal)}</strong></li>`).join("")}</ul><div class="detail-total"><span>Total</span><span>${money.format(sale.total)}</span></div><p class="modal-description">Arquivo: venda_${sale.venda_id}.json</p><div class="form-actions"><button class="primary" data-action="close">Fechar</button></div>`,
  );
}

document.addEventListener("click", async (event) => {
  const accessChoice = event.target.closest("[data-access-mode]");
  if (accessChoice && !busy) {
    const usuario = main.querySelector('[name="usuario"]')?.value || "";
    showAccess(accessChoice.dataset.accessMode);
    main.querySelector('[name="usuario"]').value = usuario;
    main.querySelector("form input").focus();
    return;
  }
  const navigation = event.target.closest(
    '[data-route="nova-venda"], a[href="#nova-venda"]',
  );
  if (navigation && currentUser && !busy) {
    latestSale = null;
    if (currentRoute() === "nova-venda") render();
  }
  const filter = event.target.closest("[data-filter]");
  if (filter && !busy) {
    saleFilter = filter.dataset.filter;
    applyFilters();
    return;
  }
  const button = event.target.closest("[data-action]");
  if (!button || button.disabled || busy) return;
  const action = button.dataset.action;
  const id = Number(button.dataset.id);
  if (action === "toggle-menu") {
    setNavigationOpen(!document.body.classList.contains("navigation-open"));
  } else if (action === "close-menu") closeNavigation();
  else if (action === "logout") {
    setBusy(true);
    try {
      await request("/api/acesso/sair", {});
      try {
        sessionStorage.removeItem(draftKey());
      } catch {
        /* Armazenamento opcional. */
      }
      history.replaceState(null, "", "#inicio");
      showAccess("entrar");
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(false);
    }
  } else if (action === "new-sale") {
    latestSale = null;
    render();
    main.focus({ preventScroll: true });
  } else if (action === "add") updateCart(id, (cart.get(id) || 0) + 1);
  else if (action === "decrease") updateCart(id, (cart.get(id) || 0) - 1);
  else if (action === "remove") updateCart(id, 0);
  else if (action === "checkout") {
    const itens = [...cart].map(([produto_id, quantidade]) => ({
      produto_id,
      quantidade,
    }));
    await mutate("/api/vendas", { itens }, (result) => {
      cart.clear();
      saveDraft();
      latestSale = result.venda.venda_id;
    });
  } else if (action === "sync" || action === "process") {
    await mutate(action === "sync" ? "/api/sincronizar" : "/api/processar", {});
  } else if (action === "refresh") {
    if (!currentUser) {
      await initialize();
      return;
    }
    setBusy(true);
    try {
      await refresh();
      toast("Dados atualizados.");
    } catch (error) {
      if (currentUser) toast(error.message, true);
    } finally {
      setBusy(false);
    }
  } else if (["new-product", "restock", "price"].includes(action))
    showForm(action, id);
  else if (action === "detail") showSale(id);
  else if (action === "close") modal.close();
});

document.addEventListener("submit", async (event) => {
  const accessForm = event.target.closest("[data-auth]");
  if (accessForm) {
    event.preventDefault();
    await authenticate(accessForm);
    return;
  }
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  if (!form.reportValidity() || busy) return;
  const data = Object.fromEntries(new FormData(form));
  for (const key of ["produto_id", "quantidade", "preco"]) {
    if (key in data) data[key] = Number(data[key]);
  }
  const endpoints = {
    "new-product": "/api/produtos",
    restock: "/api/reposicoes",
    price: "/api/precos",
  };
  const result = await mutate(endpoints[form.dataset.form], data, () =>
    modal.close(),
  );
  if (result && form.dataset.form === "new-product")
    showForm("price", data.produto_id);
});

document.addEventListener("change", (event) => {
  if (event.target.id === "show-password") {
    main
      .querySelectorAll('input[name="senha"], input[name="confirmacao"]')
      .forEach((input) => {
        input.type = event.target.checked ? "text" : "password";
      });
    return;
  }
  if (busy) return;
  if (!event.target.matches("[data-quantity]")) return;
  const id = Number(event.target.dataset.quantity);
  const value = Number(event.target.value);
  if (!event.target.value || value < 1) {
    event.target.value = cart.get(id);
    toast(
      "A quantidade mínima é 1. Use o botão de remover para excluir o item.",
      true,
    );
    return;
  }
  updateCart(id, value);
  if (event.target.isConnected) event.target.value = cart.get(id);
});

document.addEventListener("input", (event) => {
  if (event.target.id !== "search") return;
  applyFilters();
});

window.addEventListener("hashchange", () => {
  if (!currentUser) {
    if (["entrar", "cadastro"].includes(location.hash.slice(1)))
      showAccess(location.hash === "#cadastro" ? "cadastrar" : "entrar");
    return;
  }
  closeNavigation();
  if (modal.open) modal.close();
  render();
  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);
});

function closeNavigation() {
  setNavigationOpen(false);
}

function setNavigationOpen(open) {
  const mobile = window.matchMedia("(max-width: 850px)").matches;
  const visible = mobile && open;
  document.body.classList.toggle("navigation-open", visible);
  document.querySelector(".app-sidebar").inert = mobile && !visible;
  document
    .querySelector(".menu-toggle")
    .setAttribute("aria-expanded", String(visible));
}

window
  .matchMedia("(max-width: 850px)")
  .addEventListener("change", closeNavigation);

document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    document.body.classList.contains("navigation-open")
  ) {
    closeNavigation();
    document.querySelector(".menu-toggle").focus();
  }
});

document.querySelectorAll("[data-nav-icon]").forEach((element) => {
  element.innerHTML = icon(element.dataset.navIcon);
});
initialize();
