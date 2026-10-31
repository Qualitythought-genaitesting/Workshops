const display = document.querySelector('[data-display]');
const expression = document.querySelector('[data-expression]');
const keypad = document.querySelector('.keypad');

const operators = {
  add: { symbol: '+', calculate: (left, right) => left + right },
  subtract: { symbol: '−', calculate: (left, right) => left - right },
  multiply: { symbol: '×', calculate: (left, right) => left * right },
  divide: { symbol: '÷', calculate: (left, right) => left / right },
};

let currentInput = '0';
let storedValue = null;
let pendingOperator = null;
let waitingForOperand = false;
let hasError = false;

function render() {
  display.textContent = currentInput;
  display.classList.toggle('display__value--error', hasError);
}

function clear() {
  currentInput = '0';
  storedValue = null;
  pendingOperator = null;
  waitingForOperand = false;
  hasError = false;
  expression.textContent = '';
  render();
}

function enterDigit(digit) {
  if (hasError || waitingForOperand) {
    currentInput = digit;
    waitingForOperand = false;
    hasError = false;
  } else if (currentInput.replace('-', '').replace('.', '').length < 12) {
    currentInput = currentInput === '0' ? digit : currentInput + digit;
  }
  render();
}

function enterDecimal() {
  if (hasError || waitingForOperand) {
    currentInput = '0.';
    waitingForOperand = false;
    hasError = false;
  } else if (!currentInput.includes('.')) {
    currentInput += '.';
  }
  render();
}

function calculate(left, right, operator) {
  if (operator === 'divide' && right === 0) {
    hasError = true;
    currentInput = 'Error';
    return null;
  }

  const result = operators[operator].calculate(left, right);
  if (!Number.isFinite(result)) {
    hasError = true;
    currentInput = 'Error';
    return null;
  }
  return Number.parseFloat(result.toPrecision(12));
}

function chooseOperator(operator) {
  if (hasError) return;

  const inputValue = Number(currentInput);
  if (pendingOperator && !waitingForOperand) {
    const result = calculate(storedValue, inputValue, pendingOperator);
    if (result === null) {
      pendingOperator = null;
      storedValue = null;
      expression.textContent = '';
      render();
      return;
    }
    currentInput = String(result);
    storedValue = result;
  } else {
    storedValue = inputValue;
  }

  pendingOperator = operator;
  waitingForOperand = true;
  expression.textContent = `${currentInput} ${operators[operator].symbol}`;
  render();
}

function equals() {
  if (!pendingOperator || waitingForOperand || hasError) return;

  const left = storedValue;
  const right = Number(currentInput);
  const operator = pendingOperator;
  const result = calculate(left, right, operator);

  expression.textContent = `${left} ${operators[operator].symbol} ${right} =`;
  pendingOperator = null;
  storedValue = null;
  waitingForOperand = true;
  if (result !== null) currentInput = String(result);
  render();
}

function runAction(action) {
  if (action === 'clear') {
    clear();
  } else if (action === 'equals') {
    equals();
  } else if (action === 'decimal') {
    enterDecimal();
  } else if (action === 'sign' && !hasError && Number(currentInput) !== 0) {
    currentInput = String(-Number(currentInput));
    render();
  } else if (action === 'percent' && !hasError) {
    currentInput = String(Number(currentInput) / 100);
    render();
  } else if (action === 'backspace' && !hasError && !waitingForOperand) {
    currentInput = currentInput.length > 1 ? currentInput.slice(0, -1) : '0';
    if (currentInput === '-') currentInput = '0';
    render();
  }
}

keypad.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button) return;

  if (button.dataset.digit !== undefined) {
    enterDigit(button.dataset.digit);
  } else if (button.dataset.operator) {
    chooseOperator(button.dataset.operator);
  } else if (button.dataset.action) {
    runAction(button.dataset.action);
  }
});

document.addEventListener('keydown', (event) => {
  if (/^\d$/.test(event.key)) {
    enterDigit(event.key);
  } else if (event.key === '.') {
    enterDecimal();
  } else if (event.key === '+') {
    chooseOperator('add');
  } else if (event.key === '-') {
    chooseOperator('subtract');
  } else if (event.key === '*') {
    chooseOperator('multiply');
  } else if (event.key === '/') {
    event.preventDefault();
    chooseOperator('divide');
  } else if (event.key === 'Enter' || event.key === '=') {
    event.preventDefault();
    equals();
  } else if (event.key === 'Backspace') {
    runAction('backspace');
  } else if (event.key === 'Escape') {
    clear();
  } else if (event.key === '%') {
    runAction('percent');
  }
});

render();
