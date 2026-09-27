"""Small, dependency-free editing model for the NMS multiline input."""

class Buffer:
    def __init__(self,text,limit=2000):
        self.text=text;self.cursor=len(text);self.anchor=self.cursor
        self.limit=limit;self.undo=[];self.redo=[]

    def state(self):return self.text,self.cursor,self.anchor
    def restore(self,state):self.text,self.cursor,self.anchor=state
    def selected(self):
        a,b=sorted((self.cursor,self.anchor));return self.text[a:b]
    def replace(self,value):
        value=value.replace('\r\n','\n').replace('\r','\n')
        a,b=sorted((self.cursor,self.anchor))
        if len(self.text)-(b-a)+len(value)>self.limit:return False
        self.undo.append(self.state());self.redo.clear()
        self.text=self.text[:a]+value+self.text[b:]
        self.cursor=self.anchor=a+len(value)
        return True
    def move(self,index,select=False):
        self.cursor=max(0,min(len(self.text),index))
        if not select:self.anchor=self.cursor
    def key(self,key,shift=False,ctrl=False):
        if ctrl and key=='A':self.anchor=0;self.cursor=len(self.text);return True
        if ctrl and key in ('Z','Y'):
            undo=key=='Z' and not shift
            src,dst=(self.undo,self.redo) if undo else (self.redo,self.undo)
            if src:dst.append(self.state());self.restore(src.pop())
            return True
        if key in ('RET','NUMPAD_ENTER'):
            if shift:self.replace('\n');return True
            return False
        if key in ('BACK_SPACE','DEL'):
            if self.cursor==self.anchor:
                self.anchor=max(0,self.cursor-1) if key=='BACK_SPACE' else min(len(self.text),self.cursor+1)
            if self.cursor!=self.anchor:self.replace('')
            return True
        if key in ('LEFT_ARROW','RIGHT_ARROW'):
            direction=-1 if key=='LEFT_ARROW' else 1
            if not shift and self.cursor!=self.anchor:
                pos=min(self.cursor,self.anchor) if direction<0 else max(self.cursor,self.anchor)
            else:
                pos=self.cursor+direction
                if ctrl:
                    pos=max(0,min(len(self.text),pos))
                    while 0<pos<len(self.text) and not self.text[pos if direction<0 else pos-1].isspace():pos+=direction
            self.move(pos,shift);return True
        start=self.text.rfind('\n',0,self.cursor)+1
        end=self.text.find('\n',self.cursor)
        if end<0:end=len(self.text)
        if key in ('HOME','END'):
            self.move((0 if key=='HOME' else len(self.text)) if ctrl else (start if key=='HOME' else end),shift)
            return True
        if key in ('UP_ARROW','DOWN_ARROW'):
            col=self.cursor-start
            if key=='UP_ARROW':
                stop=max(0,start-1);begin=self.text.rfind('\n',0,stop)+1
            else:
                begin=min(len(self.text),end+1);stop=self.text.find('\n',begin)
                if stop<0:stop=len(self.text)
            self.move(min(begin+col,stop),shift);return True
        return False

    def rows(self,columns):
        result=[];start=0
        for line in self.text.split('\n'):
            for offset in range(0,max(1,len(line)),columns):
                result.append((start+offset,line[offset:offset+columns]))
            start+=len(line)+1
        return result
