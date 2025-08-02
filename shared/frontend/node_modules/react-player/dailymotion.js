
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/DailyMotion').default
      module.exports = createReactPlayer([{
        key: 'dailymotion',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    