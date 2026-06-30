let%expect_test "reviewable output" =
  print_endline "artifact hash: stable";
  [%expect {| artifact hash: stable |}]
