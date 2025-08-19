import { Scene } from '../../arkanalyzer/src/Scene';
import { BaseEdge, BaseNode, BaseExplicitGraph, NodeID  } from '../../arkanalyzer/src/core/graph/BaseExplicitGraph';
import { Stmt } from '../../arkanalyzer/src/core/base/Stmt'
import { Value } from '../../arkanalyzer/src/core/base/Value'
import { ClassSignature, MethodSignature } from '../../arkanalyzer/src/core/model/ArkSignature';
import { GraphPrinter } from '../../arkanalyzer/src/save/GraphPrinter';
import { PrinterBuilder } from '../../arkanalyzer/src/save/PrinterBuilder';
import { ArkClass, JsonPrinter, ViewTree, ViewTreeNode } from '../../arkanalyzer/src';
import fs from 'fs';

export type Method = MethodSignature;
export type Class = ClassSignature;

// export type CallSiteID = number;
export type FuncID = number;
type StmtSet = Set<Stmt>;


export enum PageTransitionGraphNodeKind {
    router, navigation, customized, backward, default
}

// export class CallSite {
//     public callStmt: Stmt;
//     public args: Value[] | undefined;
//     public calleeFuncID: FuncID;
//     public callerFuncID: FuncID;

//     constructor(s: Stmt, a: Value[] | undefined, ce: FuncID, cr: FuncID) {
//         this.callStmt = s;
//         this.args = a;
//         this.calleeFuncID = ce;
//         this.callerFuncID = cr;
//     }
// }
// export class PTGSite extends CallSite {
// }


export class PTGEdge extends BaseEdge {
    constructor(src: PTGNode, dst: PTGNode) {
        super(src, dst, 0);
    }
    getSrcPTGNode(): PTGNode {
        return this.getSrcNode() as PTGNode;
    }

    getDstPTGNode(): PTGNode {
        return this.getDstNode() as PTGNode;
    }
}

export class PTGNode extends BaseNode {
    private module: string;
    private page: string;
    private pageAlias = "";
    private clazz: Class;
    private viewTree: ViewTree | undefined;

    constructor(id: number, m: string, p: string, c: ArkClass, v: ViewTree | undefined) {
        super(id, PageTransitionGraphNodeKind.default);
        this.module = m;
        this.page = p;
        this.clazz = c.getSignature();
        this.viewTree = v; 
    }

    setModule(m: string) {
        this.module = m;
    }

    public getModule(): string {
        return this.module;
    }

    setPageAlias(p: string) {
        this.pageAlias = p;
    }

    public getPageAlias(): string  {
        return this.pageAlias;
    }

    public getPagePath(): string {
        return this.page;   
    }

    getClassOfPage(): Class {
        return this.clazz;
    }

    getViewTreeOfPage(): ViewTree | undefined {
        return this.viewTree;
    }

    public getDotLabel(): string {
        let label: string = 'ID: ' + this.getID() + '\n';
        label = label + this.page;
        return label;
    }
}

export class PageTransitionGraph extends BaseExplicitGraph {
    private scene: Scene;
    private callPairToEdgeMap: Map<string, PTGEdge> = new Map();
    private classToPTGNodeMap: Map<string, NodeID> = new Map();
    private pathToPTGNodeMap: Map<string, NodeID> = new Map();

    constructor(s: Scene) {
        super();
        this.scene = s;
    }

    //get Info
    public getGraphName(): string {
        return 'PTG';
    }

    public getPTGNodes() {
        let nodes = new Array<PTGNode>();
        for(let i =0; i < this.nodeNum; i++) {
            let node = this.getNode(i);
            if(node instanceof PTGNode) {
                nodes.push(node);
            }
        }
        return nodes;
    }

    public getClassToPTGNodeMap(): Map<string, NodeID> {
        return this.classToPTGNodeMap;
    }

    public getPathToPTGNodeMap(): Map<string, NodeID> {
        return this.pathToPTGNodeMap;
    }
    
    public getCallEdgeByPair(srcID: NodeID, dstID: NodeID): PTGEdge | undefined {
        let key: string = this.getCallPairString(srcID, dstID);
        return this.callPairToEdgeMap.get(key);
    }

    public getCallPairString(srcID: number, dstID: number): string {
        return `${srcID}-${dstID}`;
    }

    addPTGNode(module: string, page: string, clazz: ArkClass, viewTree: ViewTree | undefined): PTGNode ;
    addPTGNode(module: string, page: string, clazz: ArkClass, viewTree: ViewTree | undefined, pageName: string): PTGNode ;

    //add Info
    public addPTGNode(module: string, page: string,  clazz: ArkClass, viewTree: ViewTree | undefined, pageName?: string): PTGNode {
        let id: NodeID = this.nodeNum;
        let ptgNode = new PTGNode(id, module, page, clazz, viewTree);
        if(pageName!=undefined){
            ptgNode.setPageAlias(pageName);
        }
        this.classToPTGNodeMap.set(clazz.getSignature().toString(), id);
        this.pathToPTGNodeMap.set(page, id);
        this.addNode(ptgNode);
        console.log('\x1b[34m%s\x1b[0m', "add PTG node: " + ptgNode.getID() + " " + ptgNode.getPagePath());
        return ptgNode;
    }

    public addPTGEdgeByName(callerCls: string, calleeCls: string, callStmt: Stmt) {
        const caller = this.getClassToPTGNodeMap().get(callerCls);
        const callee = this.getClassToPTGNodeMap().get(calleeCls);
        // console.log("caller: "+ caller  + " callee: "+ callee);
        if(caller != undefined && callee != undefined)
            this.addPTGEdgeByID(caller, callee, callStmt);
    }

    public addPTGEdgeByID(callerID: NodeID, calleeID: NodeID, callStmt: Stmt) {
        let callerNode = this.getNode(callerID) as PTGNode;
        let calleeNode = this.getNode(calleeID) as PTGNode;

        let callEdge = this.getCallEdgeByPair(callerNode.getID(), calleeNode.getID());
        if (callEdge === undefined) {
            callEdge = new PTGEdge(callerNode, calleeNode);
            callEdge.getSrcNode().addOutgoingEdge(callEdge);
            callEdge.getDstNode().addIncomingEdge(callEdge);
            this.callPairToEdgeMap.set(this.getCallPairString(callerNode.getID(), calleeNode.getID()), callEdge);
            callerNode.addOutgoingEdge(callEdge);
            calleeNode.addIncomingEdge(callEdge);
            console.log('\x1b[32m%s\x1b[0m',`addPTGEdge: ${callerNode.getPagePath()} -> ${calleeNode.getPagePath()}`);
        }
    }
   

    public dumpDot(name: string, entry?: FuncID): void {
        let printer = new GraphPrinter<this>(this);
        if (entry) {
            printer.setStartID(entry);
        }
        PrinterBuilder.dump(printer, name);
    }

    public dumpJson(outputFileName: string): void {
        // 自定义 replacer 函数
        const replacer = (key: string, value: any) => {
            if (key === 'viewTree') {
                let list = new Array<string>();
                this.getViewTreeString((value as ViewTree).getRoot()!, list);
                return list; 
            }
            if (key === 'outEdges') {
                let list = new Array<string>();
                for(const edge of value as PTGEdge[] ){
                    list.push(edge.getSrcPTGNode().getPagePath() +" -> "+ edge.getDstPTGNode().getPagePath())
                }
                return list;
            }
            if (key === 'inEdges') {
                let list = new Array<string>();
                for(const edge of value as PTGEdge[] ){
                    list.push(edge.getSrcPTGNode().getPagePath() +" -> "+ edge.getDstPTGNode().getPagePath())
                }
                return list;
            }
            return value;
        };

        const jsonData = JSON.stringify(this.getPTGNodes(), replacer, 2);
        // 将 JSON 数据写入文件
        fs.writeFile(outputFileName, jsonData, 'utf8', (err) => {
            if (err) {
                console.error('写入文件时出错:', err);
            } else {
                console.log('数据已成功保存到 person.json');
            }
        });
    }
    public getViewTreeString(node: ViewTreeNode, list: Array<string>) {
        let attrStr = "";
        for(let atttr of node.attributes){
            attrStr += "["+atttr[0] + "@@" +atttr[1]+"] ";
        }
        // console.log(attrStr);
        list.push("key="+node.name+ "， attr= " + attrStr);
        if ( node.children.length > 0) {
            for(const child of node.children){
                this.getViewTreeString(child, list);
            }
        }
    }
    
}
    