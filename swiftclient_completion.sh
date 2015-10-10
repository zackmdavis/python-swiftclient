_swiftclient_commands() {
    echo "delete download list post stat upload capabilities tempurl auth"
}

_swiftclient_completion() {
    if [ $COMP_CWORD -eq 1 ]; then
        COMPREPLY=( $( compgen -W "$(_swiftclient_commands)" ${COMP_WORDS[COMP_CWORD]} ) )
    fi
}

complete -F _swiftclient_completion swift
