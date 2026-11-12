// Prospecção: pane do Hermes Desktop. Texto fixo até a Task 8 trazer a lista de leads.
// Carregado sem build: só o runtime JSX e o SDK do desktop; sem cores fixas.
import { jsx } from 'react/jsx-runtime';

const TITLE = 'Prospecção';

function ProspeccaoPane() {
  return jsx('p', { children: TITLE });
}

export default {
  id: 'prospeccao',
  name: TITLE,
  register(ctx) {
    ctx.register({
      id: 'prospeccao',
      area: 'panes',
      title: TITLE,
      data: { title: TITLE, placement: 'main' },
      render: () => jsx(ProspeccaoPane, {}),
    });
  },
};
