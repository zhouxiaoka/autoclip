
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/Vidyard').default
      module.exports = createReactPlayer([{
        key: 'vidyard',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    