
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/Vimeo').default
      module.exports = createReactPlayer([{
        key: 'vimeo',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    