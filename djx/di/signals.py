from blinker import signal, Signal

boot: Signal= signal('di.boot')
init: Signal = signal('di.init')
ready: Signal = signal('di.ready')