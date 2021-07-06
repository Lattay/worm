function! s:test_this()

  let l:test_name = expand('%:t:r')

  split
  exec 'term pytest worm/test/test_worm.py::test_' . l:test_name

endfunction


command! Test call s:test_this()
